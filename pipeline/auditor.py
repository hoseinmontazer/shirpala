import re
from typing import Dict, Any, Tuple, List, Optional
from .config import AUDIT_MIN_SCORE, MIN_BODY_WORD_COUNT

ZWNJ = "\u200c"

AI_REFUSAL_PATTERNS = [
    r'as an ai\b',
    r'i cannot fulfill',
    r'i am an ai\b',
    r'as a language model',
    r'به عنوان یک مدل هوش مصنوعی',
    r'به عنوان یک مدل زبان',
    r'متاسفم،? من قادر به',
    r'من یک مدل زبانی هستم',
    r'i do not have real-time information'
]

PERSIAN_CLICHES = [
    r'امروزه با پیشرفت (فناوری|تکنولوژی)',
    r'در دنیای پرشتاب امروز',
    r'در این مقاله قصد داریم',
    r'به بررسی یکی از آخرین تحولات مطرح شده',
    r'در این پست وبلاگ به بررسی',
]

ENGLISH_CLICHES = [
    r'in today\'s fast-paced world',
    r'in this article,? we will delve',
    r'in this blog post,? we will explore',
    r'in the ever-evolving landscape',
]

def normalize_persian_text(text: str) -> str:
    """Normalize Arabic characters to Persian and enforce clean typography."""
    if not text:
        return ""

    # Replace Arabic Kaf and Yeh with Persian equivalents
    text = text.replace("ك", "ک").replace("ي", "ی")

    # Remove unwanted HTML wrappers that disrupt Hugo layout
    text = re.sub(r'<div[^>]*dir=["\']?rtl["\']?[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'</div>', '', text, flags=re.IGNORECASE)

    # Enforce Half-Space (ZWNJ) for verbal prefixes "می " and "نمی "
    text = re.sub(r'\b(می|نمی)\s+([^\s\d\W]+)', r'\1' + ZWNJ + r'\2', text)

    # Enforce Half-Space for plural and comparative suffixes
    text = re.sub(r'([^\s\d\W]+)\s+(ها|های|تر|ترین|ام|ات|اش|مان|تان|شان)\b', r'\1' + ZWNJ + r'\2', text)

    # Clean double spaces
    text = re.sub(r'[ \t]+', ' ', text)
    # Clean excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()

def normalize_english_text(text: str) -> str:
    """Clean and normalize English text."""
    if not text:
        return ""
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def audit_single_lang_data(
    data: Dict[str, Any],
    lang: str = "fa",
    source_url: str = "",
    min_score: int = AUDIT_MIN_SCORE
) -> Tuple[bool, int, Dict[str, Any], List[str]]:
    """
    Audit and clean a single language section (either 'fa' or 'en').
    """
    score = 100
    notes = []
    cleaned = dict(data)
    is_fa = (lang == "fa")

    # 1. Title Audit
    title = cleaned.get("title", "").strip()
    if not title:
        score -= 40
        notes.append("CRITICAL: Title is missing or empty.")
    elif len(title) < 10:
        score -= 15
        notes.append(f"WARNING: Title is too short ({len(title)} chars; min 10).")
    elif len(title) > 160:
        score -= 10
        notes.append(f"WARNING: Title is too long ({len(title)} chars; max 160).")

    cleaned["title"] = normalize_persian_text(title) if is_fa else normalize_english_text(title)

    # 2. Description Audit
    desc = cleaned.get("description", "").strip()
    if not desc:
        score -= 20
        notes.append("WARNING: Description is missing.")
        if is_fa:
            cleaned["description"] = (cleaned.get("title", "") + " - بررسی و تحلیل تخصصی")[:150]
        else:
            cleaned["description"] = (cleaned.get("title", "") + " - Comprehensive technical review")[:150]
    else:
        norm_desc = normalize_persian_text(desc) if is_fa else normalize_english_text(desc)
        cleaned["description"] = norm_desc[:250]

    # 3. Tags & Categories Audit
    tags = cleaned.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not tags:
        score -= 10
        tags = ["DevOps", "Infrastructure"]
        notes.append("NOTICE: No tags provided; defaulted to ['DevOps', 'Infrastructure'].")
    cleaned["tags"] = [normalize_persian_text(t) if is_fa else normalize_english_text(t) for t in tags[:7]]

    categories = cleaned.get("categories", [])
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",") if c.strip()]
    if not categories:
        categories = ["کوبرنتیز و ابری"] if is_fa else ["Cloud & Infrastructure"]
    cleaned["categories"] = [normalize_persian_text(c) if is_fa else normalize_english_text(c) for c in categories[:3]]

    # 4. Content Body Audit
    body = cleaned.get("content_markdown", "")
    if not body:
        score -= 50
        notes.append("CRITICAL: Article body is empty.")
    else:
        # Check for AI refusal phrases
        for pat in AI_REFUSAL_PATTERNS:
            if re.search(pat, body, re.IGNORECASE):
                score -= 60
                notes.append(f"CRITICAL: Found AI refusal phrase matching '{pat}'.")

        # Word count check
        words = body.split()
        if len(words) < MIN_BODY_WORD_COUNT:
            score -= 25
            notes.append(f"WARNING: Body is too short ({len(words)} words; min required is {MIN_BODY_WORD_COUNT}).")

        # Check for cliches
        cliches = PERSIAN_CLICHES if is_fa else ENGLISH_CLICHES
        for pat in cliches:
            if re.search(pat, body, re.IGNORECASE):
                score -= 15
                notes.append(f"WARNING: Body contains generic cliché phrase matching '{pat}'.")

        # Code block balance check
        code_fence_count = body.count("```")
        if code_fence_count % 2 != 0:
            score -= 20
            notes.append("WARNING: Unbalanced markdown code fences (``` count is odd).")
            body += "\n```\n"

        # Check for heading structure
        if "##" not in body:
            score -= 10
            notes.append("NOTICE: Content lacks subheadings (##).")

        cleaned["content_markdown"] = normalize_persian_text(body) if is_fa else normalize_english_text(body)

    # 5. Source Link Audit
    link = cleaned.get("link", "") or source_url
    if not link or not link.startswith(("http://", "https://")):
        score -= 10
        notes.append("WARNING: Invalid or missing source link.")
    cleaned["link"] = link

    final_score = max(0, min(100, score))
    is_approved = final_score >= min_score
    return is_approved, final_score, cleaned, notes

def audit_and_clean_post(
    post_data: Dict[str, Any],
    source_url: str = "",
    min_score: int = AUDIT_MIN_SCORE
) -> Tuple[bool, int, Dict[str, Any], List[str]]:
    """
    Audit and quality-check generated content before publishing.
    Supports both bilingual format ({fa: {...}, en: {...}, slug: ...})
    and legacy single-language format.
    
    Returns:
        (is_approved, score, cleaned_post_data, audit_notes)
    """
    # Check if bilingual structure is present
    if "fa" in post_data and "en" in post_data:
        raw_slug = post_data.get("slug", "").strip()
        if not raw_slug:
            raw_title = post_data["en"].get("title") or post_data["fa"].get("title", "")
            raw_slug = re.sub(r'[^a-zA-Z0-9]+', '-', raw_title).strip('-').lower() or "tech-update"
        slug = re.sub(r'[^a-zA-Z0-9\-_]+', '-', raw_slug).strip('-').lower()
        if not slug:
            slug = "tech-update"

        source_link = post_data.get("link", "") or source_url
        source_name = post_data.get("source_name", "")

        # Audit Persian
        fa_input = dict(post_data["fa"])
        fa_input["slug"] = slug
        fa_input["link"] = source_link
        fa_input["source_name"] = source_name
        fa_appr, fa_score, fa_clean, fa_notes = audit_single_lang_data(
            fa_input, lang="fa", source_url=source_link, min_score=min_score
        )

        # Audit English
        en_input = dict(post_data["en"])
        en_input["slug"] = slug
        en_input["link"] = source_link
        en_input["source_name"] = source_name
        en_appr, en_score, en_clean, en_notes = audit_single_lang_data(
            en_input, lang="en", source_url=source_link, min_score=min_score
        )

        overall_score = min(fa_score, en_score)
        is_approved = fa_appr and en_appr

        all_notes = []
        for n in fa_notes:
            all_notes.append(f"[FA] {n}")
        for n in en_notes:
            all_notes.append(f"[EN] {n}")

        if is_approved:
            all_notes.append(f"PASS: Bilingual post passed audit (Score: {overall_score}/100, FA: {fa_score}, EN: {en_score}).")
        else:
            all_notes.append(f"HOLD: Bilingual post failed audit (Score: {overall_score}/100, FA: {fa_score}, EN: {en_score}).")

        cleaned_bilingual = {
            "slug": slug,
            "source_name": source_name,
            "link": source_link,
            "fa": fa_clean,
            "en": en_clean
        }

        return is_approved, overall_score, cleaned_bilingual, all_notes

    # Fallback: Single language legacy audit
    raw_slug = post_data.get("slug", "").strip()
    if not raw_slug:
        raw_slug = re.sub(r'[^a-zA-Z0-9]+', '-', post_data.get("title", "")).strip('-').lower() or "tech-post"
    slug = re.sub(r'[^a-zA-Z0-9\-_]+', '-', raw_slug).strip('-').lower()

    single_input = dict(post_data)
    single_input["slug"] = slug or "tech-post"
    is_appr, score, cleaned, notes = audit_single_lang_data(
        single_input, lang="fa", source_url=source_url, min_score=min_score
    )
    cleaned["slug"] = slug or "tech-post"
    return is_appr, score, cleaned, notes
