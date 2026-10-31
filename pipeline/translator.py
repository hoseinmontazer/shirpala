import json
import re
import urllib.request
import urllib.error
from typing import Dict, Any, Optional
from .config import GEMINI_API_KEY, GEMINI_MODEL
from .db import record_translation

PROMPT_TEMPLATE = """You are a senior DevOps / Systems Engineer and chief editor for "شیرپلا" (Shirpala), a premier Persian technical blog focusing on Linux, Cloud, Kubernetes, Systems Architecture, and DevOps.

Your task is to take this technical news/article and synthesize it into a high-quality, professional technical article written in fluent Persian.

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
4. Formatting:
   - Output clean GitHub-flavored markdown.
   - Code blocks with appropriate syntax highlighting language (e.g., ```yaml, ```bash, ```go).
   - DO NOT wrap the markdown in raw HTML tags like `<div dir="rtl">`. Hugo handles RTL automatically.

Return ONLY a valid JSON object matching this exact structure:
{{
  "title": "Persian technical title",
  "description": "1-2 sentence meta description in Persian",
  "slug": "kebab-case-english-slug-describing-topic",
  "categories": ["Primary Category in Persian or English"],
  "tags": ["Tag1", "Tag2", "Tag3"],
  "content_markdown": "Full article body in markdown"
}}
"""

def generate_mock_translation(article: Dict[str, Any]) -> Dict[str, Any]:
    """Fallback generator when GEMINI_API_KEY is not provided (for local testing)."""
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

def call_gemini_api(prompt: str) -> Optional[str]:
    """Call Gemini API using google-genai SDK or direct REST API."""
    if not GEMINI_API_KEY:
        return None

    # Try official google-genai SDK first
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Call gemini-3.8-flash model
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
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
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            res_json = json.loads(resp.read().decode("utf-8"))
            text = res_json["candidates"][0]["content"]["parts"][0]["text"]
            return text
    except Exception as e:
        print(f"[Translator] Gemini REST API call failed: {e}")
        return None

def translate_article(article: Dict[str, Any]) -> Dict[str, Any]:
    """Translate and adapt an article to Persian."""
    prompt = PROMPT_TEMPLATE.format(
        source_name=article.get("source_name", "Technical Source"),
        title=article.get("title", ""),
        url=article.get("url", ""),
        summary=article.get("summary", "")
    )

    result_json = None
    if GEMINI_API_KEY:
        raw_response = call_gemini_api(prompt)
        if raw_response:
            try:
                # Strip potential markdown code fences if model returned them
                cleaned = re.sub(r'^```json\s*', '', raw_response.strip())
                cleaned = re.sub(r'```$', '', cleaned.strip())
                result_json = json.loads(cleaned)
            except Exception as e:
                print(f"[Translator] Error parsing Gemini JSON response: {e}")

    if not result_json:
        if not GEMINI_API_KEY:
            print("[Translator] GEMINI_API_KEY not found in environment; using local mock adapter.")
        else:
            print("[Translator] API generation failed; falling back to local adapter.")
        result_json = generate_mock_translation(article)

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
