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

def prepare_audio_script(post_data: Dict[str, Any]) -> str:
    """
    Prepare a concise, natural Persian speech narration script from post metadata.
    Designed for smooth reading by Piper / Persian TTS models.
    """
    title = post_data.get("title", "").strip()
    description = post_data.get("description", "").strip()
    source_name = post_data.get("source_name", "").strip()

    # Clean punctuation and brackets that could stumble TTS
    title_clean = re.sub(r'[\(\)\[\]\{\}\<\>_`*#]', '', title).strip()
    desc_clean = re.sub(r'[\(\)\[\]\{\}\<\>_`*#]', '', description).strip()

    parts = ["خلاصه صوتی وبلاگ شیرپلا."]
    if source_name:
        parts.append(f"منبع خبر: {source_name}.")
    if title_clean:
        parts.append(f"موضوع: {title_clean}.")
    if desc_clean:
        parts.append(f"{desc_clean}")

    script = " ".join(parts).strip()
    # Normalize spaces
    script = re.sub(r'\s+', ' ', script)
    # Keep length reasonable (~1 minute audio)
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

    # Use ProxyHandler({}) to ensure internal LAN and domain requests are not trapped by local proxy
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

    # If bytes are already MP3 (ID3 or MPEG sync bits) or no ffmpeg available
    is_wav = raw_bytes.startswith(b'RIFF')
    if not is_wav or not ffmpeg_bin:
        with open(output_mp3, "wb") as f:
            f.write(raw_bytes)
        return True

    # Convert WAV to MP3 using ffmpeg
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

def _fallback_edge_tts(script: str, output_mp3: Path) -> bool:
    """Fallback to edge-tts if remote Nexus TTS is unreachable."""
    try:
        import asyncio
        import edge_tts

        async def _synthesize():
            comm = edge_tts.Communicate(script, "fa-IR-FaridNeural")
            await comm.save(str(output_mp3))

        asyncio.run(_synthesize())
        return output_mp3.exists() and output_mp3.stat().st_size > 0
    except Exception as e:
        print(f"[AudioTTS] edge-tts fallback failed: {e}")
        return False

def generate_post_audio(
    post_data: Dict[str, Any],
    output_dir: Path = AUDIO_OUTPUT_DIR
) -> Optional[str]:
    """
    Generate an audio version (MP3) of the post using Piper TTS on NexusLLM.
    Returns relative URL path (e.g., /audio/posts/<slug>.mp3) or None.
    """
    if not TTS_ENABLED:
        return None

    slug = post_data.get("slug", "post")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_file = output_dir / f"{slug}.mp3"

    script = prepare_audio_script(post_data)
    print(f"[AudioTTS] Generating Persian speech audio for '{slug}' via NexusLLM '{TTS_MODEL}' (voice: {TTS_VOICE})...")

    # Priority 1: NexusLLM Piper API
    audio_bytes = _call_nexus_tts(script, model=TTS_MODEL, voice=TTS_VOICE)

    # Priority 2: NexusLLM fish-speech if piper fails
    if not audio_bytes and TTS_MODEL != "fish-speech":
        print("[AudioTTS] Retrying with secondary model 'fish-speech' on Nexus...")
        audio_bytes = _call_nexus_tts(script, model="fish-speech", voice="default")

    if audio_bytes:
        success = _convert_to_mp3(audio_bytes, audio_file)
        if success and audio_file.exists():
            size_kb = audio_file.stat().st_size // 1024
            print(f"[AudioTTS] ✅ Audio generated via Nexus API: {audio_file.name} ({size_kb} KB)")
            return f"/audio/posts/{slug}.mp3"

    # Priority 3: Local edge-tts fallback
    print("[AudioTTS] Attempting local fallback for speech generation...")
    if _fallback_edge_tts(script, audio_file):
        size_kb = audio_file.stat().st_size // 1024
        print(f"[AudioTTS] ✅ Audio generated via fallback: {audio_file.name} ({size_kb} KB)")
        return f"/audio/posts/{slug}.mp3"

    print(f"[AudioTTS] ❌ Could not generate audio for '{slug}'.")
    return None
