import subprocess
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from .config import POSTS_OUTPUT_DIR, HUGO_SITE_DIR, HUGO_REBUILD_ON_PUBLISH
from .db import record_audit_result

def format_hugo_post(
    post_data: Dict[str, Any],
    is_approved: bool,
    audit_score: int,
    pub_date: Optional[str] = None,
    audio_url: Optional[str] = None
) -> str:
    """Format markdown content with clean Hugo TOML frontmatter and optional audio player."""
    date_str = pub_date or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    draft_val = "false" if is_approved else "true"
    
    title = post_data.get("title", "").replace('"', '\\"')
    description = post_data.get("description", "").replace('"', '\\"')
    author = post_data.get("author", "شیرپلا").replace('"', '\\"')
    link = post_data.get("link", "").replace('"', '\\"')

    # Format arrays
    tags_formatted = ", ".join(f'"{t.strip()}"' for t in post_data.get("tags", []))
    categories_formatted = ", ".join(f'"{c.strip()}"' for c in post_data.get("categories", []))

    audio_frontmatter = f'audio = ["{audio_url}"]\n' if audio_url else ""

    toml_frontmatter = f"""+++
title = "{title}"
date = {date_str}
draft = {draft_val}
description = "{description}"
tags = [{tags_formatted}]
categories = [{categories_formatted}]
author = "{author}"
link = "{link}"
{audio_frontmatter}audit_score = {audit_score}
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
    audio_url: Optional[str] = None
) -> Path:
    """Write post to Hugo content directory and optionally trigger rebuild."""
    POSTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = post_data.get("slug", "tech-post")
    
    file_path = POSTS_OUTPUT_DIR / f"{slug}.md"
    if file_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        file_path = POSTS_OUTPUT_DIR / f"{slug}-{timestamp}.md"

    content = format_hugo_post(post_data, is_approved, audit_score, audio_url=audio_url)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[Publisher] Saved post to {file_path} (draft={not is_approved}, score={audit_score}, audio={bool(audio_url)})")

    # Record in database
    if article_id:
        record_audit_result(
            article_id=article_id,
            audit_score=audit_score,
            audit_notes="\n".join(audit_notes),
            is_approved=is_approved,
            output_file=str(file_path)
        )

    # Trigger rebuild if configured
    if HUGO_REBUILD_ON_PUBLISH and is_approved:
        trigger_hugo_build()

    return file_path

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
            print("[Publisher] Triggering Docker Hugo build...")
            res = subprocess.run(
                ["docker", "run", "--rm", "-v", f"{HUGO_SITE_DIR}:/site", "hugo", "hugo", "--baseURL=https://blog.knowly.ir/"],
                check=False,
                capture_output=True
            )
            if res.returncode == 0:
                print("[Publisher] Docker Hugo build completed successfully.")
            else:
                print(f"[Publisher] Docker Hugo build stderr: {res.stderr.decode('utf-8', errors='ignore')}")
        except Exception as e:
            print(f"[Publisher] Docker build error: {e}")
