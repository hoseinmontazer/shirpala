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

PROMPT_TEMPLATE = """You are a Principal Systems Engineer and Chief Editor for "نولی" (Knowly - blog.knowly.ir), a premier bilingual (Persian & English) technical publication for senior DevOps, SRE, Linux, and Cloud Infrastructure Engineers.

Analyze the source material and author BOTH:
1. An in-depth, authoritative, deeply technical article in fluent Persian (`fa`).
2. A comprehensive, rigorous technical article in professional English (`en`).

Source Material:
- Source: {source_name}
- Original Title: {title}
- Original URL: {url}
- Source Content:
{summary}

STRICT EDITORIAL & QUALITY PRINCIPLES:
1. BAN GENERIC CLICHÉS:
   - In Persian: NEVER start with filler phrases like "در دنیای امروز با پیشرفت فناوری" or "در این مقاله قصد داریم...".
   - In English: NEVER start with generic AI filler like "In today's fast-paced digital landscape...".
   - Start immediately with the core technical reality, the specific architectural challenge, or system bottleneck.
2. ARCHITECTURAL DEPTH & RIGOR:
   - Explain the "Why" and "How" under the hood. What was the limitation or inefficiency in the prior design (e.g., syscall overhead, thread contention, network serialization, memory allocation bottlenecks)?
   - How does the new approach solve it? Detail underlying mechanisms (e.g., eBPF maps, lock-free queues, kernel scheduler algorithms, zero-copy buffers, CRDs).
3. PRESERVE CONCRETE DATA & EXAMPLES:
   - Retain all benchmarks, performance percentages, latency percentiles (p95, p99), version numbers, and concrete metrics mentioned in the source.
   - Include realistic YAML configuration, shell commands, or code snippets in both articles.
4. ACCURATE TECHNICAL TERMINOLOGY:
   - For Persian: Keep standard English technical terms in parentheses on first mention in `content_markdown` (e.g., گذرگاه داده سریع (XDP / eXpress Data Path), تخصیص پویای منابع (Dynamic Resource Allocation)).
5. SRE PRODUCTION TAKEAWAYS:
   - Provide concrete, actionable insights for production clusters: observability/metrics considerations, potential migration traps, security implications, or configuration tips.
6. CONTENT VOLUME:
   - Both the Persian and English articles must be extensive (at least 350-500 words each, with 3-4 structured `##` sections).
7. IMMERSIVE & NATURAL PODCAST AUDIO SCRIPTS (audio_script):
   - You MUST author an in-depth, natural conversational podcast narration script (`audio_script`) for each language (between 450 and 700 words, representing ~3 to 5 minutes of comprehensive listening).
   - Conversational & Human Podcast Tone:
     * Write like an experienced, articulate tech podcast host having a lively conversation with senior engineers, NOT like a robot reading a dry textbook.
     * Use natural conversational connectors (e.g., "بیایید ببینیم در پشت صحنه چه اتفاقی می‌افتد", "شاید بپرسید چرا این تغییر انقدر حیاتیه؟", "در واقع در سیستم‌های پرترافیک...").
   - Spoken Narrative Flow:
     1. Host Introduction & Opening Hook:
        Warm, energetic welcome (FA: "سلام و درود به شنوندگان پادکست فنی نولی. با یک اپیزود تخصصی دیگر در حوزه مهندسی زیرساخت همراه شما هستیم. در این قسمت می‌خواهیم به کالبدشکافی عمیق..." / EN: "Welcome to the Knowly Engineering Podcast. In today's technical deep dive...").
     2. The Real-World Dilemma / Production Battlefield:
        Set the scene. Explain why the legacy architecture or old tooling failed under high traffic, scale, or edge cases. What pain points did platform engineers and SREs suffer?
     3. Deep Dive into the Inner Mechanics:
        Explain how the new system, kernel mechanism, algorithm, or controller operates under the hood. Walk through the workflow step-by-step with clear mental models.
     4. Concrete Numbers, Latency & Benchmarks:
        Quote concrete metrics from the article: p99 latency improvements, CPU/memory reduction, throughput gains, or release version numbers.
     5. 3 Battle-Tested SRE & Production Takeaways:
        Share 3 practical, actionable tips for cluster administrators: flags to set, pitfalls to watch for, or metrics to scrape.
     6. Friendly Outro & Call to Action:
        Conclude with a warm sign-off inviting listeners to view the architecture diagrams, YAML manifests, and full article at blog.knowly.ir.
   - CRITICAL RULES FOR PERSIAN AUDIO SCRIPT (`fa.audio_script`):
     * ABSOLUTELY NO PERSONAL NAMES: DO NOT say any individual's personal name (e.g. NEVER say "من حسین منتظر هستم"). The voice speaks on behalf of the Knowly technical publication ("پادکست فنی نولی").
     * DO NOT use ANY raw English characters or English words (e.g., NO "Kubernetes", NO "StatefulSet", NO "Deployment", NO "eBPF", NO "SRE").
     * ALWAYS write «پادکاست» (with explicit Alif) or «رادیو نولی» (NEVER write «پادکست» without Alif, because speech synthesizers misread it as padkost).
     * ALWAYS write «گره»، «گره‌ها»، «گره‌های»، «گره‌هایی» for cluster nodes (NEVER «نود/نودها/نودهایی» — TTS reads them as the number 90). Keep «نود» ONLY for the number ninety («نود و نه»، «نود درصد»).
     * ALWAYS write «سِروِر» when referring to machines (NEVER unvocalized «سرور»).
     * ALWAYS write «کِلاستِر» / «کلستر» as «کِلاستِر», «کانتِینِر», «دِواپس», «کیوب‌لِت» (vocalized spellings).
     * NEVER leave raw English brand domains like blog.knowly.ir — say «وب‌سایت بلاگ نولی».
     * Phonetically transliterate ALL technical terms into Persian script:
       «کوبرنتیز»، «دیپلوی‌منت»، «استیت‌فول‌ست»، «دیمن‌ست»، «ای‌بی‌پی‌اف»، «اس‌آر‌ای»، «داکر»، «پاد»، «پادها»، «کرنل»، «لینوکس»، «سی‌پی‌یو»، «رم»، «هوش مصنوعی»، «سیگ اپس»، «اوپن‌تله‌متری»، «پرومتئوس».
     * Write short, rhythmic, flowing sentences with frequent commas (،) so the speech synthesizer breathes naturally with human intonation.
     * Absolutely NO markdown fences, NO asterisks, NO hashes, NO bullet points, NO parentheses.
   - FOR ENGLISH AUDIO SCRIPT (`en.audio_script`):
     * 450-700 words of conversational, highly engaging spoken narrative without markdown syntax, following the same 6-part podcast structure.

Return ONLY a valid JSON object matching this exact structure:
{{
  "slug": "english-kebab-case-slug",
  "fa": {{
    "title": "عنوان جذاب، دقیق و مهندسی به زبان فارسی",
    "description": "خلاصه دو جمله‌ای بسیار دقیق و فنی برای متادیتا",
    "categories": ["کوبرنتیز و ابری"],
    "tags": ["تگ۱", "تگ۲", "Tag3"],
    "content_markdown": "متن مشروح و عمیق مقاله به زبان فارسی شامل مقدمه مستقیم، تحلیل معماری با تیترهای ##، کدهای پیکربندی/YAML، و جمع‌بندی عملیاتی.",
    "audio_script": "متن مشروح و طبیعی پادکست فنی نولی (Knowly) به زبان فارسی با ساختار ۶ بخشی: مقدمه گرم پادکست نولی (بدون نام شخص)، پیش‌زمینه و چالش مقیاس‌پذیری در پروداکشن، کالبدشکافی عمیق معماری، اعداد و بنچمارک‌های ملموس، ۳ درس عملیاتی، و جمع‌بندی نهایی (بین ۴۵۰ تا ۷۰۰ کلمه برای ۳ تا ۵ دقیقه گویندگی رسا و کامل بدون هیچ کلمه لاتین)."
  }},
  "en": {{
    "title": "Deep Technical Title in English",
    "description": "Two-sentence technical overview and metadata summary in English",
    "categories": ["Kubernetes & Cloud"],
    "tags": ["Tag1", "Tag2", "Tag3"],
    "content_markdown": "Comprehensive, authoritative in-depth technical article in English with ## headings, architecture analysis, YAML/code snippets, and SRE takeaways.",
    "audio_script": "Deep, immersive 450-700 word podcast narration in conversational spoken English with Knowly podcast intro (no personal names), architectural deep dive, benchmark stats, 3 SRE takeaways, and outro (~3 to 5 minutes of listening)."
  }}
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
                    "You are a Principal Systems Engineer and Chief Editor for Shirpala bilingual tech publication. "
                    "Output ONLY a valid JSON object matching the requested schema with keys: slug, fa, en."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "max_tokens": 6000,
        "temperature": 0.3,
        # Disables reasoning loop in vLLM Qwen so all tokens are used for output
        "chat_template_kwargs": {"enable_thinking": False}
    }

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
                with opener.open(req, timeout=120) as resp:
                    res_data = json.loads(resp.read().decode("utf-8"))
                    message = res_data["choices"][0]["message"]
                    content = message.get("content")
                    if content and content.strip():
                        return content
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

    endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            return res_json["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        print(f"[Translator] Gemini REST API call failed: {e}")
        return None

def generate_mock_translation(article: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback bilingual generator when no LLM API is available."""
    title = article.get("title", "Modern Systems & Cloud Infrastructure Update")
    slug = re.sub(r'[^a-zA-Z0-9]+', '-', article.get("title", "tech-post")).strip('-').lower()[:40] or "tech-update"
    
    fa_body = f"""تحلیل و بررسی عمیق آخرین تحولات فنی مطرح شده توسط **{article.get('source_name', 'منبع مرجع')}**.

## معماری و چالش‌های فنی

موضوع اصلی پیرامون «{article.get('title', '')}» است. در سیستم‌های ابری توزیع‌شده مدرن، بهینه‌سازی منابع و ایزوله‌سازی کارآمد دغدغه بنیادین تیم‌های SRE است.

{article.get('summary', 'این گزارش شامل بررسی معماری و بهبودهای فنی سرویس‌ها می‌باشد.')}

## نکات کلیدی برای تیم‌های دواپس

- بهینه‌سازی بار پردازشی و کاهش سربار I/O
- ارتقای الگوهای امنیتی و مانیتورینگ جامع
- استفاده از خطوط لوله مدرن CI/CD برای استقرار بدون توقف

---
منبع اصلی: [{article.get('title', 'مشاهده مقاله اصلی')}]({article.get('url', '#')})
"""

    en_body = f"""In-depth technical breakdown of recent architectural updates reported by **{article.get('source_name', 'Reference Source')}**.

## Architecture & System Challenges

This article investigates "{article.get('title', '')}". Modern distributed cloud platforms demand rigorous isolation, predictable resource consumption, and low tail latencies.

{article.get('summary', 'Detailed engineering breakdown and system considerations.')}

## Key Takeaways for SRE & Platform Teams

- Processing overhead minimization and zero-copy data paths
- Hardened security boundaries and fine-grained observability
- Continuous deployment resilience and zero-downtime rolling upgrades

---
Original Source: [{article.get('title', 'View Source Article')}]({article.get('url', '#')})
"""

    return {
        "slug": slug,
        "source_name": article.get("source_name", ""),
        "link": article.get("url", ""),
        "fa": {
            "title": f"گزارش فنی: {title}",
            "description": f"تحلیل و بررسی تحولات {title} از دیدگاه مهندسی نرم‌افزار و زیرساخت.",
            "categories": [article.get("source_category", "کوبرنتیز و ابری")],
            "tags": article.get("default_tags", ["DevOps", "Infrastructure"]),
            "content_markdown": fa_body
        },
        "en": {
            "title": f"Technical Report: {title}",
            "description": f"Comprehensive architectural review of {title} for platform and DevOps engineers.",
            "categories": ["Cloud & Infrastructure"],
            "tags": article.get("default_tags", ["DevOps", "Infrastructure"]),
            "content_markdown": en_body
        }
    }

def translate_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate bilingual (Persian & English) articles from source material.
    Returns:
        {
          "slug": str,
          "source_name": str,
          "link": str,
          "fa": {"title": ..., "description": ..., "categories": [...], "tags": [...], "content_markdown": ...},
          "en": {"title": ..., "description": ..., "categories": [...], "tags": [...], "content_markdown": ...}
        }
    """
    prompt = PROMPT_TEMPLATE.format(
        source_name=article.get("source_name", "Technical Source"),
        title=article.get("title", ""),
        url=article.get("url", ""),
        summary=article.get("summary", "")
    )

    result_json = None

    # Priority 1: DariaSystem NexusLLM
    if LLM_PROVIDER == "nexusllm" or (not result_json and NEXUSLLM_API_KEY):
        print(f"[Translator] Using NexusLLM ({NEXUSLLM_MODEL}) for bilingual synthesis...")
        raw_output = call_nexusllm_api(prompt)
        if raw_output:
            result_json = extract_json_object(raw_output)

    # Priority 2: Google Gemini
    if not result_json and (LLM_PROVIDER == "gemini" or GEMINI_API_KEY):
        print(f"[Translator] Using Gemini ({GEMINI_MODEL}) for bilingual synthesis...")
        raw_output = call_gemini_api(prompt)
        if raw_output:
            result_json = extract_json_object(raw_output)

    # Priority 3: Mock fallback
    if not result_json:
        print("[Translator] Falling back to local bilingual adapter.")
        result_json = generate_mock_translation(article)

    # Normalize structure if model returned flat keys instead of nested {fa, en}
    slug = result_json.get("slug")
    if not slug:
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', article.get("title", "post")).strip('-').lower()[:40] or "tech-update"

    source_name = article.get("source_name", "")
    link = article.get("url", "")

    if "fa" in result_json and "en" in result_json:
        bilingual_data = {
            "slug": slug,
            "source_name": source_name,
            "link": link,
            "fa": result_json["fa"],
            "en": result_json["en"]
        }
    else:
        # Backward compatibility conversion
        bilingual_data = {
            "slug": slug,
            "source_name": source_name,
            "link": link,
            "fa": {
                "title": result_json.get("title", article.get("title", "")),
                "description": result_json.get("description", ""),
                "categories": result_json.get("categories", ["کوبرنتیز و ابری"]),
                "tags": result_json.get("tags", ["DevOps"]),
                "content_markdown": result_json.get("content_markdown", "")
            },
            "en": {
                "title": article.get("title", "Technical Article"),
                "description": result_json.get("description", ""),
                "categories": ["Cloud & Infrastructure"],
                "tags": ["DevOps"],
                "content_markdown": result_json.get("content_markdown", "")
            }
        }

    # Record translation in database if article_id exists
    if "article_id" in article:
        record_translation(
            article_id=article["article_id"],
            translated_title=bilingual_data["fa"].get("title", ""),
            description=bilingual_data["fa"].get("description", ""),
            translated_content=bilingual_data["fa"].get("content_markdown", ""),
            slug=slug,
            tags=",".join(bilingual_data["fa"].get("tags", [])),
            categories=",".join(bilingual_data["fa"].get("categories", []))
        )

    return bilingual_data
