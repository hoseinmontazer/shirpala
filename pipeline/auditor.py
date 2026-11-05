import re
from typing import Dict, Any, Tuple, List
from .config import AUDIT_MIN_SCORE, MIN_BODY_WORD_COUNT

ZWNJ = "\u200c"

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

def audit_and_clean_post(
    post_data: Dict[str, Any],
    source_url: str = "",
    min_score: int = AUDIT_MIN_SCORE
) -> Tuple[bool, int, Dict[str, Any], List[str]]:
    """
    Audit and quality-check generated content before publishing.
    
    Returns:
        (is_approved, score, cleaned_post_data, audit_notes)
    """
    score = 100
    notes = []
    cleaned = dict(post_data)

    # 1. Title Audit
    title = cleaned.get("title", "").strip()
    if not title:
        score -= 40
        notes.append("CRITICAL: Title is missing or empty.")
    elif len(title) < 10:
        score -= 15
        notes.append("WARNING: Title is too short (< 10 chars).")
    elif len(title) > 160:
        score -= 10
        notes.append("WARNING: Title is too long (> 160 chars).")
    cleaned["title"] = normalize_persian_text(title)

    # 2. Description Audit
    desc = cleaned.get("description", "").strip()
    if not desc:
        score -= 20
        notes.append("WARNING: Description is missing.")
        # Auto-generate a description from body if missing
        cleaned["description"] = (cleaned.get("title", "") + " - بررسی و گزارش فنی")[:150]
    else:
        cleaned["description"] = normalize_persian_text(desc)[:250]

    # 3. Slug Audit
    slug = cleaned.get("slug", "").strip()
    if not slug:
        slug = re.sub(r'[^a-zA-Z0-9]+', '-', title).strip('-').lower() or "post"
    slug = re.sub(r'[^a-zA-Z0-9\-_]+', '-', slug).strip('-').lower()
    cleaned["slug"] = slug or "tech-update"

    # 4. Tags & Categories Audit
    tags = cleaned.get("tags", [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    if not tags:
        score -= 10
        notes.append("NOTICE: No tags provided; defaulted to ['DevOps', 'Technology'].")
        tags = ["DevOps", "Technology"]
    cleaned["tags"] = [normalize_persian_text(t) for t in tags[:7]]

    categories = cleaned.get("categories", [])
    if isinstance(categories, str):
        categories = [c.strip() for c in categories.split(",") if c.strip()]
    if not categories:
        categories = ["تکنولوژی"]
    cleaned["categories"] = [normalize_persian_text(c) for c in categories[:3]]

    # 5. Content Body Audit
    body = cleaned.get("content_markdown", "")
    if not body:
        score -= 50
        notes.append("CRITICAL: Article body is empty.")
    else:
        # Check for AI refusal phrases
        ai_refusal_patterns = [
            r'as an ai\b',
            r'i cannot fulfill',
            r'به عنوان یک مدل هوش مصنوعی',
            r'متاسفم،? من قادر به',
            r'i do not have real-time information'
        ]
        for pat in ai_refusal_patterns:
            if re.search(pat, body, re.IGNORECASE):
                score -= 60
                notes.append(f"CRITICAL: Found AI refusal phrase matching '{pat}'.")

        # Word count check
        words = body.split()
        if len(words) < MIN_BODY_WORD_COUNT:
            score -= 25
            notes.append(f"WARNING: Body is too short ({len(words)} words; min required is {MIN_BODY_WORD_COUNT}).")

        # Check for generic cliches
        cliche_patterns = [
            r'امروزه با پیشرفت (فناوری|تکنولوژی)',
            r'در دنیای پرشتاب امروز',
            r'در این مقاله قصد داریم',
            r'به بررسی یکی از آخرین تحولات مطرح شده',
        ]
        for pat in cliche_patterns:
            if re.search(pat, body):
                score -= 15
                notes.append(f"WARNING: Body contains generic cliché phrase matching '{pat}'.")

        # Code block balance check
        code_fence_count = body.count("```")
        if code_fence_count % 2 != 0:
            score -= 20
            notes.append("WARNING: Unbalanced markdown code fences (``` count is odd).")
            # Auto-close code block
            body += "\n```\n"

        # Check for heading structure
        if "##" not in body:
            score -= 10
            notes.append("NOTICE: Content lacks subheadings (##).")

        # Clean typography in body
        cleaned["content_markdown"] = normalize_persian_text(body)

    # 6. Source Link Audit
    link = cleaned.get("link", "") or source_url
    if not link or not link.startswith(("http://", "https://")):
        score -= 15
        notes.append("WARNING: Invalid or missing source link.")
    cleaned["link"] = link

    # Final score determination
    final_score = max(0, min(100, score))
    is_approved = final_score >= min_score

    if is_approved:
        notes.append(f"PASS: Post passed quality audit with score {final_score}/100.")
    else:
        notes.append(f"HOLD: Post failed audit with score {final_score}/100 (Threshold: {min_score}). Setting draft=true.")

    return is_approved, final_score, cleaned, notes
