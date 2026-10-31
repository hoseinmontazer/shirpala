import json
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
    """Prepare a concise, clear speech narration script from post metadata."""
    title = post_data.get("title", "")
    description = post_data.get("description", "")
    source_name = post_data.get("source_name", "Tech Brief")
    
    # Clean script for speech
    script = f"Shirpala Audio Brief. Source: {source_name}. Title: {title}. Overview: {description}."
    
    # Limit length to avoid excessive audio generation latency (around 500 chars / ~1 min)
    return script[:800]

def generate_post_audio(
    post_data: Dict[str, Any],
    output_dir: Path = AUDIO_OUTPUT_DIR
) -> Optional[str]:
    """
    Generate an audio version (MP3) of the post using Kokoro TTS on NexusLLM.
    Returns relative URL path (e.g., /audio/posts/<slug>.mp3) or None.
    """
    if not TTS_ENABLED:
        return None

    if not NEXUSLLM_API_KEY:
        print("[AudioTTS] NEXUSLLM_API_KEY not configured; skipping TTS generation.")
        return None

    slug = post_data.get("slug", "post")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_file = output_dir / f"{slug}.mp3"

    script = prepare_audio_script(post_data)
    print(f"[AudioTTS] Generating speech audio using model '{TTS_MODEL}' (voice: {TTS_VOICE})...")

    endpoint = f"{NEXUSLLM_BASE_URL}/audio/speech"
    payload = {
        "model": TTS_MODEL,
        "input": script,
        "voice": TTS_VOICE
    }

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {NEXUSLLM_API_KEY}",
            "Content-Type": "application/json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            audio_bytes = response.read()
            
            # Sanity check: Ensure valid audio bytes (not JSON error)
            if audio_bytes.startswith(b'{"detail"') or audio_bytes.startswith(b'{"error"'):
                print(f"[AudioTTS] Error from TTS endpoint: {audio_bytes.decode('utf-8', errors='ignore')}")
                return None

            with open(audio_file, "wb") as f:
                f.write(audio_bytes)

            file_size_kb = len(audio_bytes) // 1024
            print(f"[AudioTTS] Audio generated successfully: {audio_file.name} ({file_size_kb} KB)")
            return f"/audio/posts/{slug}.mp3"
    except Exception as e:
        print(f"[AudioTTS] Audio generation failed: {e}")
        return None

