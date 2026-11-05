import os
import re
import html
import requests
from pathlib import Path
from typing import Dict, Any, Optional, Union, List
from .config import (
    BASE_DIR,
    TELEGRAM_ENABLED,
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHANNEL_ID,
    TELEGRAM_SEND_AUDIO,
    TELEGRAM_PROXY,
    SITE_BASE_URL,
    AUDIO_OUTPUT_DIR
)

def _get_proxies() -> Optional[Dict[str, str]]:
    """Resolve proxy configuration for Telegram requests."""
    proxy = TELEGRAM_PROXY or os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY") or os.getenv("ALL_PROXY")
    if proxy:
        return {"http": proxy, "https": proxy}
    return None

def _format_hashtags(tags: List[str]) -> str:
    """Format tags as Telegram hashtags."""
    formatted = []
    for tag in tags:
        t = tag.strip().replace(" ", "_").replace("-", "_")
        # Remove special characters from hashtag
        t = re.sub(r'[^\w\u0600-\u06FF]', '', t)
        if t and not t.isdigit():
            formatted.append(f"#{t}")
    return " ".join(formatted[:6])

def _build_telegram_caption(
    title: str,
    description: str,
    slug: str,
    tags: List[str],
    is_podcast: bool = True
) -> str:
    """Construct an engaging, beautifully formatted HTML message for Telegram."""
    fa_url = f"{SITE_BASE_URL}/fa/posts/{slug}/"
    en_url = f"{SITE_BASE_URL}/en/posts/{slug}/"
    hashtags = _format_hashtags(tags)

    header = "🎙 <b>پادکست و تحلیل فنی شیرپالا</b>" if is_podcast else "🚀 <b>مقاله جدید در پایگاه فنی شیرپالا</b>"
    channel_display = TELEGRAM_CHANNEL_ID if TELEGRAM_CHANNEL_ID.startswith("@") else "کانال شیرپالا"

    # Base structure
    caption_template = (
        f"{header}\n\n"
        f"📌 <b>{html.escape(title)}</b>\n\n"
        f"📝 {html.escape(description)}\n\n"
        f"🌐 <b>مطالعه مقاله و کدهای معماری:</b>\n"
        f"🔗 <a href=\"{fa_url}\">نسخه فارسی در وب‌سایت</a>\n"
        f"🇬🇧 <a href=\"{en_url}\">English Architecture Deep-Dive</a>\n\n"
        f"🏷 {hashtags}\n"
        f"📡 {channel_display}"
    )

    # Telegram caption limit is 1024 characters. Truncate description if needed.
    if len(caption_template) > 1020:
        excess = len(caption_template) - 1010
        truncated_desc = description[:-excess].rstrip() + "..."
        caption_template = (
            f"{header}\n\n"
            f"📌 <b>{html.escape(title)}</b>\n\n"
            f"📝 {html.escape(truncated_desc)}\n\n"
            f"🌐 <b>مطالعه مقاله و کدهای معماری:</b>\n"
            f"🔗 <a href=\"{fa_url}\">نسخه فارسی در وب‌سایت</a>\n"
            f"🇬🇧 <a href=\"{en_url}\">English Architecture Deep-Dive</a>\n\n"
            f"🏷 {hashtags}\n"
            f"📡 {channel_display}"
        )

    return caption_template

def broadcast_to_telegram(
    post_data: Dict[str, Any],
    audio_urls: Optional[Dict[str, Optional[str]]] = None,
    slug: Optional[str] = None
) -> bool:
    """
    Broadcast a newly published article and its podcast audio to the Telegram Channel.
    Respects TELEGRAM_ENABLED and gracefully handles proxies and network conditions.
    """
    if not TELEGRAM_ENABLED:
        print("[Telegram] Telegram broadcast is currently disabled (TELEGRAM_ENABLED=false).")
        return True

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHANNEL_ID:
        print("[Telegram] ⚠️ TELEGRAM_BOT_TOKEN or TELEGRAM_CHANNEL_ID is not configured in .env.")
        return False

    slug_val = slug or post_data.get("slug", "post")

    # Extract Persian post metadata (preferred) or general
    fa_data = post_data.get("fa", post_data)
    title = fa_data.get("title", "مقاله جدید شیرپالا")
    description = fa_data.get("description", "")
    tags = fa_data.get("tags", [])

    proxies = _get_proxies()
    base_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    # Check for local Persian audio file
    audio_file_path: Optional[Path] = None
    if TELEGRAM_SEND_AUDIO:
        candidate_fa = AUDIO_OUTPUT_DIR / f"{slug_val}-fa.mp3"
        if candidate_fa.exists() and candidate_fa.stat().st_size > 1000:
            audio_file_path = candidate_fa
        elif audio_urls and audio_urls.get("fa"):
            # Check if relative path points to local static folder
            rel = audio_urls["fa"].lstrip("/")
            local_cand = BASE_DIR / "blog" / "static" / rel
            if local_cand.exists():
                audio_file_path = local_cand

    # 1. Send Audio with Rich Caption if audio is present
    if audio_file_path and audio_file_path.exists():
        caption = _build_telegram_caption(title, description, slug_val, tags, is_podcast=True)
        print(f"[Telegram] Uploading podcast audio to channel ({TELEGRAM_CHANNEL_ID}): {audio_file_path.name}...")

        try:
            with open(audio_file_path, "rb") as f:
                resp = requests.post(
                    f"{base_api}/sendAudio",
                    data={
                        "chat_id": TELEGRAM_CHANNEL_ID,
                        "caption": caption,
                        "parse_mode": "HTML",
                        "title": title[:64],
                        "performer": "رادیو شیرپالا | Shirpala Radio",
                    },
                    files={"audio": (audio_file_path.name, f, "audio/mpeg")},
                    proxies=proxies,
                    timeout=90
                )
            result = resp.json()
            if result.get("ok"):
                print(f"[Telegram] ✅ Successfully published podcast & post to channel {TELEGRAM_CHANNEL_ID}!")
                return True
            else:
                print(f"[Telegram] ⚠️ sendAudio API returned error: {result.get('description')}")
                print("[Telegram] Falling back to text message...")
        except Exception as e:
            print(f"[Telegram] ⚠️ Error sending audio: {e}. Falling back to text message...")

    # 2. Fallback to rich text message (sendMessage)
    text_message = _build_telegram_caption(title, description, slug_val, tags, is_podcast=False)
    print(f"[Telegram] Sending article text message to channel ({TELEGRAM_CHANNEL_ID})...")

    try:
        resp = requests.post(
            f"{base_api}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHANNEL_ID,
                "text": text_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            },
            proxies=proxies,
            timeout=30
        )
        result = resp.json()
        if result.get("ok"):
            print(f"[Telegram] ✅ Successfully sent article update to {TELEGRAM_CHANNEL_ID}!")
            return True
        else:
            print(f"[Telegram] ❌ sendMessage API error: {result.get('description')}")
            return False
    except Exception as e:
        print(f"[Telegram] ❌ Telegram connection error: {e}")
        if not proxies:
            print("[Telegram] 💡 Tip: If you are behind a firewall or in an environment where api.telegram.org is filtered, set TELEGRAM_PROXY=socks5://127.0.0.1:1080 (or your proxy) in .env.")
        return False

def test_telegram_connection() -> bool:
    """Diagnostic tool to verify bot credentials and channel permissions."""
    print("=" * 60)
    print("🔍 Testing Telegram Bot Connection & Channel Configuration...")
    print(f"  • Enabled in Config : {TELEGRAM_ENABLED}")
    print(f"  • Bot Token Status  : {'Configured (' + TELEGRAM_BOT_TOKEN[:10] + '...)' if TELEGRAM_BOT_TOKEN else 'MISSING'}")
    print(f"  • Channel Target    : {TELEGRAM_CHANNEL_ID or 'MISSING'}")
    print(f"  • Proxy Configured  : {TELEGRAM_PROXY or 'None (Direct / Env)'}")
    print("=" * 60)

    if not TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN is empty. Please set it in .env.")
        return False

    proxies = _get_proxies()
    base_api = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

    # Step 1: getMe
    try:
        print("\n[Step 1/2] Checking Bot Token with getMe...")
        resp = requests.get(f"{base_api}/getMe", proxies=proxies, timeout=15)
        data = resp.json()
        if not data.get("ok"):
            print(f"❌ Bot token is invalid: {data.get('description')}")
            return False
        bot_user = data["result"]
        print(f"✅ Bot Connected: @{bot_user.get('username')} ({bot_user.get('first_name')})")
    except Exception as e:
        print(f"❌ Failed to reach api.telegram.org: {e}")
        print("💡 Ensure internet access or configure TELEGRAM_PROXY in your .env file.")
        return False

    # Step 2: Send test message to channel
    if not TELEGRAM_CHANNEL_ID:
        print("\nℹ️ No TELEGRAM_CHANNEL_ID set. Skipping channel message test.")
        return True

    print(f"\n[Step 2/2] Sending test message to channel '{TELEGRAM_CHANNEL_ID}'...")
    try:
        test_text = (
            "🚀 <b>اتصال بات رادیو و وبلاگ شیرپالا با موفقیت برقرار شد.</b>\n\n"
            "این یک پیام آزمایشی برای تایید دسترسی بات به کانال است.\n"
            "از این پس خلاصه مقالات و پادکست‌های صوتی به صورت خودکار در این کانال منتشر خواهند شد.\n\n"
            "🌐 https://blog.knowly.ir"
        )
        resp = requests.post(
            f"{base_api}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHANNEL_ID,
                "text": test_text,
                "parse_mode": "HTML"
            },
            proxies=proxies,
            timeout=20
        )
        res_data = resp.json()
        if res_data.get("ok"):
            print(f"🎉 SUCCESS! Test message sent to {TELEGRAM_CHANNEL_ID}.")
            return True
        else:
            print(f"❌ Failed to send message to channel: {res_data.get('description')}")
            print("💡 Common causes:")
            print("   1. The bot has not been added to the channel as an Administrator.")
            print("   2. The bot does not have 'Post Messages' permission in the channel.")
            print("   3. Channel ID/username is misspelled (e.g. should start with '@').")
            return False
    except Exception as e:
        print(f"❌ Error during channel send test: {e}")
        return False

if __name__ == "__main__":
    import sys
    test_telegram_connection()
