import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Union
from .config import (
    POSTS_FA_DIR,
    POSTS_EN_DIR,
    POSTS_OUTPUT_DIR,
    HUGO_SITE_DIR,
    HUGO_REBUILD_ON_PUBLISH
)
from .db import record_audit_result

def _toml_multiline_string(value: str) -> str:
    """Encode a long narration script as a TOML multiline literal string."""
    text = (value or "").strip()
    if not text:
        return ""
    # Avoid breaking the delimiter if the model ever emits triple quotes.
    safe = text.replace('"""', "'''")
    return f'"""\n{safe}\n"""'


def format_hugo_post(
    post_data: Dict[str, Any],
    is_approved: bool,
    audit_score: int,
    pub_date: Optional[str] = None,
    audio_url: Optional[str] = None,
    lang: str = "fa",
    translation_key: Optional[str] = None
) -> str:
    """Format markdown content with clean Hugo TOML frontmatter and audio player."""
    date_str = pub_date or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    draft_val = "false" if is_approved else "true"
    
    title = post_data.get("title", "").replace('"', '\\"')
    description = post_data.get("description", "").replace('"', '\\"')
    
    # Default editorial author
    default_author = "تیم فنی نولی" if lang == "fa" else "Knowly Engineering Team"
    author = post_data.get("author", default_author).replace('"', '\\"')
    link = post_data.get("link", "").replace('"', '\\"')

    # Format arrays
    tags_formatted = ", ".join(f'"{t.strip()}"' for t in post_data.get("tags", []))
    categories_formatted = ", ".join(f'"{c.strip()}"' for c in post_data.get("categories", []))

    trans_key_line = f'translationKey = "{translation_key}"\n' if translation_key else ""
    audio_frontmatter = f'audio = ["{audio_url}"]\n' if audio_url else ""

    # Persist spoken narration so TTS regen does not fall back to mixed article body.
    audio_script_raw = post_data.get("audio_script", "")
    audio_script_block = ""
    encoded_script = _toml_multiline_string(audio_script_raw)
    if encoded_script:
        audio_script_block = f"audio_script = {encoded_script}\n"

    toml_frontmatter = f"""+++
title = "{title}"
date = {date_str}
draft = {draft_val}
description = "{description}"
tags = [{tags_formatted}]
categories = [{categories_formatted}]
author = "{author}"
link = "{link}"
{trans_key_line}{audio_frontmatter}{audio_script_block}audit_score = {audit_score}
+++
{post_data.get("content_markdown", "").strip()}
"""
    return toml_frontmatter

def publish_post(
    post_data: Dict[str, Any],
    is_approved: bool,
    audit_score: int,
    audit_notes: List[str],
    article_id: Optional[int] = None,
    audio_url: Optional[Union[str, Dict[str, Optional[str]]]] = None
) -> Union[Path, Dict[str, Path]]:
    """
    Write post to Hugo content directories and optionally trigger rebuild.
    Handles bilingual articles ({fa: ..., en: ..., slug: ...})
    and legacy single-language articles.
    """
    # 1. Bilingual Publishing
    if "fa" in post_data and "en" in post_data:
        POSTS_FA_DIR.mkdir(parents=True, exist_ok=True)
        POSTS_EN_DIR.mkdir(parents=True, exist_ok=True)

        slug = post_data.get("slug", "tech-post")
        pub_date = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Determine audio per language
        fa_audio = None
        en_audio = None
        if isinstance(audio_url, dict):
            fa_audio = audio_url.get("fa")
            en_audio = audio_url.get("en")
        elif isinstance(audio_url, str):
            fa_audio = audio_url

        # Persian Post
        fa_file = POSTS_FA_DIR / f"{slug}.md"
        fa_content = format_hugo_post(
            post_data=post_data["fa"],
            is_approved=is_approved,
            audit_score=audit_score,
            pub_date=pub_date,
            audio_url=fa_audio,
            lang="fa",
            translation_key=slug
        )
        with open(fa_file, "w", encoding="utf-8") as f:
            f.write(fa_content)

        # English Post
        en_file = POSTS_EN_DIR / f"{slug}.md"
        en_content = format_hugo_post(
            post_data=post_data["en"],
            is_approved=is_approved,
            audit_score=audit_score,
            pub_date=pub_date,
            audio_url=en_audio,
            lang="en",
            translation_key=slug
        )
        with open(en_file, "w", encoding="utf-8") as f:
            f.write(en_content)

        print(f"[Publisher] Saved bilingual posts:\n  • FA: {fa_file.name} (audio={bool(fa_audio)})\n  • EN: {en_file.name} (audio={bool(en_audio)})")

        if article_id:
            record_audit_result(
                article_id=article_id,
                audit_score=audit_score,
                audit_notes="\n".join(audit_notes),
                is_approved=is_approved,
                output_file=f"{fa_file};{en_file}"
            )

        if HUGO_REBUILD_ON_PUBLISH and is_approved:
            trigger_hugo_build()

        return {"fa": fa_file, "en": en_file}

    # 2. Legacy Single Post Publishing
    POSTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = post_data.get("slug", "tech-post")
    single_file = POSTS_OUTPUT_DIR / f"{slug}.md"

    single_audio = audio_url if isinstance(audio_url, str) else None
    content = format_hugo_post(
        post_data=post_data,
        is_approved=is_approved,
        audit_score=audit_score,
        audio_url=single_audio,
        lang="fa",
        translation_key=slug
    )
    with open(single_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[Publisher] Saved single post: {single_file.name} (draft={not is_approved}, score={audit_score})")

    if article_id:
        record_audit_result(
            article_id=article_id,
            audit_score=audit_score,
            audit_notes="\n".join(audit_notes),
            is_approved=is_approved,
            output_file=str(single_file)
        )

    if HUGO_REBUILD_ON_PUBLISH and is_approved:
        trigger_hugo_build()

    return single_file

def trigger_hugo_build():
    """Trigger Hugo build via host binary or docker if present."""
    hugo_bin = shutil.which("hugo")
    if hugo_bin:
        try:
            print("[Publisher] Triggering local Hugo build...")
            subprocess.run([hugo_bin, "--baseURL=https://blog.knowly.ir/"], cwd=HUGO_SITE_DIR, check=True, capture_output=True)
            print("[Publisher] Hugo build completed successfully.")
            return
        except Exception as e:
            print(f"[Publisher] Local Hugo build error: {e}")

    docker_bin = shutil.which("docker")
    if docker_bin:
        try:
            res = subprocess.run(["docker", "exec", "hugo-builder", "hugo", "--baseURL=https://blog.knowly.ir/"], capture_output=True, check=False)
            if res.returncode == 0:
                print("[Publisher] Triggered Hugo build inside hugo-builder container.")
                return
        except Exception:
            pass
