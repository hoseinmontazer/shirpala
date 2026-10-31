import json
import re
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

PROMPT_TEMPLATE = """You are a senior DevOps / Systems Engineer and chief editor for "شیرپلا" (Shirpala), a premier Persian technical blog focusing on Linux, Cloud, Kubernetes, Systems Architecture, and DevOps.

Your task is to take this technical news/article and synthesize it into a comprehensive, high-quality technical article written in fluent Persian.

Source Information:
- Source: {source_name}
- Original Title: {title}
- Original URL: {url}
- Source Content/Summary: {summary}

Guidelines for Writing:
1. Tone: Professional, authoritative, insightful, and readable. DO NOT perform robotic literal word-by-word machine translation.
2. Terminology: Use accepted Iranian tech industry terminology. Keep standard English technical terms in parentheses on first mention (e.g., کوبرنتیز (Kubernetes), ران‌تایم (Runtime), مدیریت حافظه (Memory Management)). NEVER translate idioms or technical names literally (e.g., do not translate "boot" as "پوتین"!).
3. Structure:
   - Strong introductory paragraph explaining the context and importance.
   - Core technical breakdown / architectural changes with subheadings (`##`).
   - Impact, practical considerations, or takeaways for developers / SREs.
   - Final conclusion and reference link back to the source.
4. Content length: Write a comprehensive, detailed article (at least 350-500 words in Persian). NEVER use placeholders like "..." or leave sections empty.
5. Formatting: Output clean GitHub-flavored markdown. Code blocks with appropriate syntax highlighting language. DO NOT wrap the markdown in raw HTML tags.

Return ONLY a valid JSON object matching this exact structure:
{{
  "title": "عنوان جذاب و دقیق به زبان فارسی",
  "description": "خلاصه دو جمله‌ای فنی و دقیق برای پیش‌نمایش و متادیتا",
  "slug": "english-kebab-case-slug",
  "categories": ["دسته‌بندی اصلی مانند لینوکس یا دواپس"],
  "tags": ["تگ ۱", "تگ ۲", "Tag3"],
  "content_markdown": "متن کامل، مشروح و غنی مقاله به زبان فارسی شامل مقدمه، تیترهای ##، تحلیل فنی، و نتیجه‌گیری"
}}
"""

def extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    """Robust JSON extraction from LLM response."""
    if not raw_text:
        return None

    cleaned = raw_text.strip()
    # Strip markdown fences if present
    if "```" in cleaned:
        cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
        cleaned = re.sub(r'```$', '', cleaned).strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except Exception:
        pass

    # Find outermost or best JSON block
    start = raw_text.find('{')
    end = raw_text.rfind('}')
    if start != -1 and end != -1 and end > start:
        candidate = raw_text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            pass

    return None

def call_nexusllm_api(prompt: str) -> Optional[str]:
    """Call DariaSystem NexusLLM chat completions endpoint (OpenAI compatible)."""
    if not NEXUSLLM_API_KEY:
        return None

    endpoint = f"{NEXUSLLM_BASE_URL}/chat/completions"
    payload = {
        "model": NEXUSLLM_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a professional Persian technical writer for Shirpala blog. "
                    "Output ONLY a valid JSON object with keys: title, description, slug, categories, tags, content_markdown."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 3500,
        "temperature": 0.3,
        "enable_thinking": False
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {NEXUSLLM_API_KEY}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            res_data = json.loads(resp.read().decode("utf-8"))
            return res_data["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[Translator] NexusLLM call failed: {e}")
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
