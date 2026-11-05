import os
import re
import json
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional
from .config import (
    NEXUSLLM_BASE_URL,
    NEXUSLLM_API_KEY,
    TTS_ENABLED,
    TTS_MODEL,
    TTS_VOICE,
    AUDIO_OUTPUT_DIR
)

def prepare_audio_script(post_data: Dict[str, Any], lang: str = "fa") -> str:
    """
    Prepare a concise, natural speech narration script from post metadata.
    Supports Persian (fa) and English (en).
    """
    title = post_data.get("title", "").strip()
    description = post_data.get("description", "").strip()
    source_name = post_data.get("source_name", "").strip()

    title_clean = re.sub(r'[\(\)\[\]\{\}\<\>_`*#]', '', title).strip()
    desc_clean = re.sub(r'[\(\)\[\]\{\}\<\>_`*#]', '', description).strip()

    if lang == "fa":
        parts = ["خلاصه صوتی وبلاگ شیرپلا."]
        if source_name:
            parts.append(f"منبع خبر: {source_name}.")
        if title_clean:
            parts.append(f"موضوع: {title_clean}.")
        if desc_clean:
            parts.append(f"{desc_clean}")
    else:
        parts = ["Shirpala Audio Brief."]
        if source_name:
            parts.append(f"Source: {source_name}.")
        if title_clean:
            parts.append(f"Topic: {title_clean}.")
        if desc_clean:
            parts.append(f"{desc_clean}")

    script = " ".join(parts).strip()
    script = re.sub(r'\s+', ' ', script)
    return script[:800]

def _call_nexus_tts(script: str, model: str, voice: str) -> Optional[bytes]:
    """Call NexusLLM /v1/audio/speech endpoint with proxy bypass."""
    if not NEXUSLLM_API_KEY:
        return None

    endpoint = f"{NEXUSLLM_BASE_URL}/audio/speech"
    payload = {
        "model": model,
        "input": script,
        "voice": voice
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {NEXUSLLM_API_KEY}",
            "Content-Type": "application/json"
        }
    )

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=60) as resp:
            audio_bytes = resp.read()
            if audio_bytes.startswith(b'{"detail"') or audio_bytes.startswith(b'{"error"'):
                print(f"[AudioTTS] Error response from Nexus: {audio_bytes.decode('utf-8', errors='ignore')}")
                return None
            return audio_bytes
    except urllib.error.HTTPError as e:
        err_body = e.read().decode('utf-8', errors='ignore')
        print(f"[AudioTTS] Nexus TTS HTTP Error {e.code}: {err_body}")
        return None
    except Exception as e:
        print(f"[AudioTTS] Nexus TTS call failed: {e}")
        return None

def _convert_to_mp3(raw_bytes: bytes, output_mp3: Path) -> bool:
    """Save audio bytes as MP3, converting with ffmpeg if source is WAV."""
    ffmpeg_bin = shutil.which("ffmpeg")

    is_wav = raw_bytes.startswith(b'RIFF')
    if not is_wav or not ffmpeg_bin:
        with open(output_mp3, "wb") as f:
            f.write(raw_bytes)
        return True

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
        tmp_wav.write(raw_bytes)
        tmp_wav_path = tmp_wav.name

    try:
        cmd = [
            ffmpeg_bin, "-y",
            "-i", tmp_wav_path,
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            str(output_mp3)
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return res.returncode == 0
    finally:
        try:
            os.remove(tmp_wav_path)
        except OSError:
            pass

def _fallback_edge_tts(script: str, output_mp3: Path, lang: str = "fa") -> bool:
    """Fallback to edge-tts if remote Nexus TTS is unreachable or for English."""
    try:
        import asyncio
        import edge_tts

        voice = "fa-IR-FaridNeural" if lang == "fa" else "en-US-AndrewMultilingualNeural"

        async def _synthesize():
            comm = edge_tts.Communicate(script, voice)
            await comm.save(str(output_mp3))

        asyncio.run(_synthesize())
        return output_mp3.exists() and output_mp3.stat().st_size > 0
    except Exception as e:
        print(f"[AudioTTS] edge-tts fallback failed ({lang}): {e}")
        return False

def generate_post_audio(
    post_data: Dict[str, Any],
    lang: str = "fa",
    output_dir: Path = AUDIO_OUTPUT_DIR
) -> Optional[str]:
    """
    Generate an audio version (MP3) of the post.
    For Persian (fa): Uses NexusLLM Piper.
    For English (en): Uses edge-tts / Nexus Piper.
    Returns relative URL path (e.g., /audio/posts/<slug>-<lang>.mp3) or None.
    """
    if not TTS_ENABLED:
        return None

    slug = post_data.get("slug", "post")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_file = output_dir / f"{slug}-{lang}.mp3"

    script = prepare_audio_script(post_data, lang=lang)
    print(f"[AudioTTS] Generating [{lang.upper()}] audio for '{slug}'...")

    if lang == "fa":
        # Priority 1 for Persian: NexusLLM Piper API
        audio_bytes = _call_nexus_tts(script, model=TTS_MODEL, voice=TTS_VOICE)
        if not audio_bytes and TTS_MODEL != "fish-speech":
            audio_bytes = _call_nexus_tts(script, model="fish-speech", voice="default")

        if audio_bytes:
            success = _convert_to_mp3(audio_bytes, audio_file)
            if success and audio_file.exists():
                size_kb = audio_file.stat().st_size // 1024
                print(f"[AudioTTS] ✅ FA Audio generated via Nexus API: {audio_file.name} ({size_kb} KB)")
                return f"/audio/posts/{slug}-fa.mp3"

        # Fallback for Persian: edge-tts
        if _fallback_edge_tts(script, audio_file, lang="fa"):
            size_kb = audio_file.stat().st_size // 1024
            print(f"[AudioTTS] ✅ FA Audio generated via fallback: {audio_file.name} ({size_kb} KB)")
            return f"/audio/posts/{slug}-fa.mp3"

    else:
        # Priority 1 for English: edge-tts (Andrew Neural)
        if _fallback_edge_tts(script, audio_file, lang="en"):
            size_kb = audio_file.stat().st_size // 1024
            print(f"[AudioTTS] ✅ EN Audio generated via edge-tts: {audio_file.name} ({size_kb} KB)")
            return f"/audio/posts/{slug}-en.mp3"

        # Fallback for English: Nexus Piper
        audio_bytes = _call_nexus_tts(script, model=TTS_MODEL, voice="en_US-lessac-medium")
        if audio_bytes:
            success = _convert_to_mp3(audio_bytes, audio_file)
            if success and audio_file.exists():
                size_kb = audio_file.stat().st_size // 1024
                print(f"[AudioTTS] ✅ EN Audio generated via Nexus: {audio_file.name} ({size_kb} KB)")
                return f"/audio/posts/{slug}-en.mp3"

    print(f"[AudioTTS] ❌ Could not generate audio for '{slug}' ({lang}).")
    return None
