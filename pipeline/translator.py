import json
import re
import time
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from .config import (
    LLM_PROVIDER,
    NEXUSLLM_BASE_URL,
    NEXUSLLM_API_KEY,
    NEXUSLLM_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL
)
from .db import record_translation

PROMPT_TEMPLATE = """You are a Principal Systems Engineer and Chief Editor for "شیرپلا" (Shirpala), a premier Persian technical publication for senior DevOps, SRE, Linux, and Cloud Infrastructure Engineers.

Your task is to analyze the source material and author a comprehensive, authoritative, deeply technical article in professional Persian.

Source Material:
- Source: {source_name}
- Original Title: {title}
- Original URL: {url}
- Source Content:
{summary}

STRICT EDITORIAL & QUALITY PRINCIPLES:
1. BAN GENERIC CLICHÉS:
   - NEVER start with robotic filler phrases like "در دنیای امروز با پیشرفت فناوری" or "در این مقاله قصد داریم به بررسی...".
   - Start immediately with the core technical reality, the specific architectural challenge, or system bottleneck.
2. ARCHITECTURAL DEPTH & RIGOR:
   - Explain the "Why" and "How" under the hood. What was the limitation or inefficiency in the prior design (e.g., syscall overhead, thread contention, network serialization, memory allocation bottlenecks)?
   - How does the new approach solve it? Detail the underlying mechanisms (e.g., eBPF maps, lock-free queues, kernel scheduler algorithms, zero-copy buffers, CRDs).
3. PRESERVE CONCRETE DATA & EXAMPLES:
   - Retain all benchmarks, performance percentages, latency percentiles (p95, p99), version numbers, and concrete metrics mentioned in the source.
   - Include realistic YAML configuration, shell commands, or code snippets wherever relevant.
4. ACCURATE TECHNICAL TERMINOLOGY:
   - Use accepted Iranian tech industry conventions. Keep standard English technical terms in parentheses on first mention (e.g., گذرگاه داده سریع (XDP / eXpress Data Path), تخصیص پویای منابع (Dynamic Resource Allocation), بازآرایی پاد (Pod Eviction)).
   - NEVER translate technical tools, flags, protocols, or names literally.
5. SRE PRODUCTION TAKEAWAYS:
   - Provide concrete, actionable insights for production clusters: observability/metrics considerations, potential migration traps, security implications, or configuration tips.
6. CONTENT VOLUME:
   - The article must be extensive, detailed, and rich (at least 450-700 Persian words with 3-4 structured `##` sections). No placeholders, no stubs.

Return ONLY a valid JSON object matching this exact structure:
{{
  "title": "عنوان جذاب، دقیق و مهندسی به زبان فارسی",
  "description": "خلاصه دو جمله‌ای بسیار دقیق، فنی و جذاب برای پیش‌نمایش و متادیتا",
  "slug": "english-kebab-case-slug",
  "categories": ["دسته‌بندی اصلی مانند کوبرنتیز و ابری، لینوکس و شبکه، یا مشاهده‌پذیری و SRE"],
  "tags": ["تگ۱", "تگ۲", "Tag3", "Tag4"],
  "content_markdown": "متن مشروح، عمیق و استاندارد مقاله به زبان فارسی شامل مقدمه مستقیم، تحلیل معماری با تیترهای ##، کدهای پیکربندی/YAML، و جمع‌بندی عملیاتی برای مهندسان زیرساخت."
}}
"""

def extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    """Robust JSON extraction from LLM response."""
    if not raw_text:
        return None

    cleaned = raw_text.strip()
    # Strip markdown code fences if present
    if "```" in cleaned:
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'```$', '', cleaned).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Find outermost JSON block
    start = raw_text.find('{')
    end = raw_text.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = raw_text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            # Clean common issues like control characters inside strings
            try:
                candidate_cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', candidate)
                return json.loads(candidate_cleaned)
            except Exception:
                pass

    return None

def call_nexusllm_api(prompt: str) -> Optional[str]:
    """Call DariaSystem NexusLLM chat completions endpoint (OpenAI compatible)."""
    if not NEXUSLLM_API_KEY:
        return None

    # Base URLs with automatic failover between domain and internal LAN IP
    base_urls = [NEXUSLLM_BASE_URL]
    if "api-nexusllm.dariasystem.com" in NEXUSLLM_BASE_URL:
        base_urls.append("http://192.168.0.200:8880/v1")
    elif "192.168.0.200" in NEXUSLLM_BASE_URL:
        base_urls.append("https://api-nexusllm.dariasystem.com/v1")

    payload = {
        "model": NEXUSLLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a senior DevOps / Systems Engineer and chief editor for Shirpala blog. "
                    "Output ONLY a valid JSON object with keys: title, description, slug, categories, tags, content_markdown."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 5000,
        "temperature": 0.3,
        # Crucial for vLLM Qwen: shuts off reasoning loop so tokens are 100% available for output
        "chat_template_kwargs": {"enable_thinking": False}
    }

    # Proxy-safe opener
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    for base_url in base_urls:
        endpoint = f"{base_url}/chat/completions"
        for attempt in range(1, 4):
            req = urllib.request.Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {NEXUSLLM_API_KEY}",
                    "Content-Type": "application/json"
                }
            )

            try:
                with opener.open(req, timeout=90) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    message = res_data["choices"][0]["message"]
                    content = message.get("content")
                    if content and content.strip():
                        return content
                    # If content is empty but reasoning exists, try extracting from reasoning
                    reasoning = message.get("reasoning")
                    if reasoning and "{" in reasoning and "}" in reasoning:
                        print("[Translator] Content was empty; using reasoning field as fallback...")
                        return reasoning
            except urllib.error.HTTPError as e:
                err_body = e.read().decode("utf-8", errors="ignore")
                print(f"[Translator] NexusLLM HTTP {e.code} (attempt {attempt}/3 at {base_url}): {err_body[:100]}")
                if e.code in (502, 503, 504) and attempt < 3:
                    time.sleep(3 * attempt)
                    continue
                break
            except Exception as e:
                print(f"[Translator] NexusLLM error (attempt {attempt}/3 at {base_url}): {e}")
                if attempt < 3:
                    time.sleep(2)
                    continue
                break

    return None

def call_gemini_api(prompt: str) -> Optional[str]:
    """Call Gemini API using google-genai SDK or direct REST API."""
    if not GEMINI_API_KEY:
        return None

    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json")
        )
        return response.text
    except ImportError:
        pass
    except Exception as e:
        print(f"[Translator] google-genai SDK call error: {e}, attempting HTTP fallback...")

    # Fallback to direct REST API
    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[Translator] Gemini REST API call failed: {e}")
        return None

def generate_mock_translation(article: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback generator when no LLM API is available."""
    title = article.get("title", "بررسی تحولات جدید در زیرساخت‌های مدرن")
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', article.get("title", "tech-post")).strip('-').lower()[:40] or "tech-update"
    
    body = f"""در این مقاله به بررسی یکی از آخرین تحولات مطرح شده در دنیای فناوری و زیرساخت می‌پردازیم که اخیراً توسط **{article.get('source_name', 'منبع مرجع')}** منتشر شده است.

## مروری بر موضوع

موضوع اصلی مطرح شده پیرامون «{article.get('title', '')}» است. با گسترش سیستم‌های توزیع‌شده و پیچیدگی زیرساخت‌های ابری، بهینه‌سازی عملکرد و مدیریت مطمئن منابع به دغدغه اصلی تیم‌های SRE و DevOps تبدیل شده است.

{article.get('summary', 'این به‌روزرسانی شامل بهبودهای کلیدی در معماری و بهره‌وری سرویس‌ها می‌باشد.')}

## نکات کلیدی و دستاوردهای فنی

- **بهینه‌سازی معماری:** ایجاد هماهنگی بیشتر میان سرویس‌ها و کاهش بار پردازشی.
- **افزایش امنیت و پایداری:** ارتقای سیاست‌های دسترسی و اطمینان از صحت عملکرد ماژول‌ها.
- **انعطاف‌پذیری در پیاده‌سازی:** سازگاری بالا با خطوط لوله CI/CD و محیط‌های ابری مدرن.

## جمع‌بندی و نتیجه‌گیری

توجه به این تغییرات و به‌کارگیری استانداردهای جدید به تیم‌ها کمک می‌کند تا سرویس‌هایی مقیاس‌پذیرتر و قابل اعتمادتر ارائه دهند. برای مطالعه جزئیات عمیق‌تر، می‌توانید گزارش اصلی را در وبسایت منبع مشاهده فرمایید.

---

منبع اصلی: [{article.get('title', 'مشاهده مقاله اصلی')}]({article.get('url', '#')})
"""
    return {
        "title": f"گزارش فنی: {title}",
        "description": f"تحلیل و بررسی آخرین تحولات پیرامون {title} از دیدگاه مهندسی نرم‌افزار و زیرساخت.",
        "slug": slug,
        "categories": [article.get("source_category", "DevOps")],
        "tags": article.get("default_tags", ["DevOps", "Infrastructure"]),
        "content_markdown": body
    }

def translate_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """Translate and adapt an article to Persian using configured LLM provider."""
    prompt = PROMPT_TEMPLATE.format(
        source_name=article.get("source_name", "Technical Source"),
        title=article.get("title", ""),
        url=article.get("url", ""),
        summary=article.get("summary", "")
    )

    result_json = None

    # Priority 1: DariaSystem NexusLLM
    if LLM_PROVIDER == "nexusllm" or (not result_json and NEXUSLLM_API_KEY):
        print(f"[Translator] Using NexusLLM ({NEXUSLLM_MODEL})...")
        raw_output = call_nexusllm_api(prompt)
        if raw_output:
            result_json = extract_json_object(raw_output)

    # Priority 2: Google Gemini
    if not result_json and (LLM_PROVIDER == "gemini" or GEMINI_API_KEY):
        print(f"[Translator] Using Gemini ({GEMINI_MODEL})...")
        raw_output = call_gemini_api(prompt)
        if raw_output:
            result_json = extract_json_object(raw_output)

    # Priority 3: Mock fallback
    if not result_json:
        print("[Translator] Falling back to local adapter.")
        result_json = generate_mock_translation(article)

    # Attach original source information
    result_json["source_name"] = article.get("source_name", "")
    result_json["link"] = article.get("url", "")

    # Record in database if article_id exists
    if "article_id" in article:
        record_translation(
            article_id=article["article_id"],
            translated_title=result_json.get("title", ""),
            description=result_json.get("description", ""),
            translated_content=result_json.get("content_markdown", ""),
            slug=result_json.get("slug", "post"),
            tags=",".join(result_json.get("tags", [])),
            categories=",".join(result_json.get("categories", []))
        )

    return result_json
