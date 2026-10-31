#!/usr/bin/env python3
"""
Script to generate neural TTS audio for Hugo blog posts.
Supports English (en) and Persian (fa) using edge-tts.
"""

import os
import re
import sys
import glob
import asyncio
import subprocess
from pathlib import Path

# Preferred neural voices
VOICES = {
    "fa": "fa-IR-FaridNeural",
    "en": "en-US-AndrewMultilingualNeural",
}

def clean_markdown_for_speech(text: str, lang: str) -> str:
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', ' ', text)
    # Remove inline code
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Convert markdown links [text](url) to just text
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove image tags ![alt](url)
    text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', text)
    # Remove header markers (#, ##, etc.)
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)
    # Remove markdown bold/italics
    text = re.sub(r'[*_]{1,3}([^*_]+)[*_]{1,3}', r'\1', text)
    # Remove blockquotes
    text = re.sub(r'^\s*>\s*', '', text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r'^\s*[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)
    # Normalize excessive newlines and whitespace
    text = re.sub(r'\n{2,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    return text.strip()

def parse_post(content: str):
    """Parse frontmatter and body from a post."""
    fm_type = None
    fm_raw = ""
    body = ""

    if content.startswith("+++"):
        parts = content.split("+++", 2)
        if len(parts) >= 3:
            fm_type = "toml"
            fm_raw = parts[1]
            body = parts[2]
    elif content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            fm_type = "yaml"
            fm_raw = parts[1]
            body = parts[2]

    title = ""
    desc = ""
    audio = None

    if fm_raw:
        # Title
        m_title = re.search(r'title\s*=\s*["\']([^"\']+)["\']', fm_raw)
        if not m_title:
            m_title = re.search(r'title:\s*["\']?([^"\n\r]+)["\']?', fm_raw)
        if m_title:
            title = m_title.group(1).strip()

        # Description
        m_desc = re.search(r'description\s*=\s*["\']([^"\']+)["\']', fm_raw)
        if not m_desc:
            m_desc = re.search(r'description:\s*["\']?([^"\n\r]+)["\']?', fm_raw)
        if m_desc:
            desc = m_desc.group(1).strip()

        # Audio
        m_audio = re.search(r'audio\s*=\s*["\']([^"\']+)["\']', fm_raw)
        if not m_audio:
            m_audio = re.search(r'audio:\s*["\']?([^"\n\r]+)["\']?', fm_raw)
        if m_audio:
            audio = m_audio.group(1).strip()

    return fm_type, fm_raw, body, title, desc, audio

def update_frontmatter_audio(content: str, fm_type: str, audio_path: str) -> str:
    """Add or update audio field in frontmatter as list (compatible with Hugo opengraph)."""
    if fm_type == "toml":
        if re.search(r'audio\s*=', content):
            return re.sub(r'audio\s*=\s*(?:\[[^\]]*\]|["\'][^"\']+["\'])', f'audio = ["{audio_path}"]', content)
        else:
            return re.sub(r'(\+\+\+[\s\S]*?)(\+\+\+)', rf'\1audio = ["{audio_path}"]\n\2', content, count=1)
    elif fm_type == "yaml":
        yaml_entry = f'audio:\n  - "{audio_path}"'
        if re.search(r'audio:\s*', content):
            return re.sub(r'audio:\s*(?:\n\s*-\s*["\']?[^"\n\r]+["\']?|["\']?[^"\n\r]+["\']?)', yaml_entry, content)
        else:
            return re.sub(r'(---[\s\S]*?)(---)', rf'\1{yaml_entry}\n\2', content, count=1)
    return content

async def synthesize_audio(text: str, voice: str, output_path: str):
    """Use edge-tts to generate audio file."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def process_file(file_path: Path, force=False):
    lang = "fa" if "/fa/" in str(file_path) else "en"
    voice = VOICES.get(lang, VOICES["en"])
    
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    fm_type, fm_raw, body, title, desc, existing_audio = parse_post(content)
    if not fm_type:
        print(f"Skipping {file_path}: No frontmatter found")
        return

    slug = file_path.stem
    audio_rel = f"/audio/{lang}/{slug}.mp3"
    audio_full = Path("blog/static") / audio_rel.lstrip("/")

    if existing_audio and audio_full.exists() and not force:
        print(f"Audio already exists for {file_path} -> {audio_rel}")
        return

    audio_full.parent.mkdir(parents=True, exist_ok=True)

    # Prepare speech text
    clean_body = clean_markdown_for_speech(body, lang)
    speech_parts = []
    if title:
        speech_parts.append(title + ".")
    if desc:
        speech_parts.append(desc + ".")
    speech_parts.append(clean_body)
    full_text = "\n\n".join(speech_parts).strip()

    if not full_text:
        print(f"No text to synthesize for {file_path}")
        return

    print(f"Generating audio for [{lang}] {file_path.name} (voice: {voice})...")
    asyncio.run(synthesize_audio(full_text, voice, str(audio_full)))
    print(f"Saved: {audio_full} ({os.path.getsize(audio_full)} bytes)")

    # Update post frontmatter
    new_content = update_frontmatter_audio(content, fm_type, audio_rel)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print(f"Updated frontmatter for {file_path}")

def main():
    base_dir = Path(__file__).resolve().parent.parent
    os.chdir(base_dir)

    posts = list(Path("blog/content").glob("*/posts/*.md"))
    print(f"Found {len(posts)} posts to process.")

    force = "--force" in sys.argv
    for post in posts:
        try:
            process_file(post, force=force)
        except Exception as e:
            print(f"Error processing {post}: {e}")

if __name__ == "__main__":
    main()
