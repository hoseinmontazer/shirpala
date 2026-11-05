import os
import re
import io
import wave
import json
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List
from .config import (
    NEXUSLLM_BASE_URL,
    NEXUSLLM_API_KEY,
    TTS_ENABLED,
    TTS_MODEL,
    TTS_VOICE,
    AUDIO_OUTPUT_DIR
)
from .text_normalizer import normalize_mixed_persian_english_text

def clean_persian_tts_script(text: str) -> str:
    """Prepare Persian text for clean, human-sounding speech synthesis using the auto-learning normalizer."""
    return normalize_mixed_persian_english_text(text, enable_auto_learning=True)

def clean_english_tts_script(text: str) -> str:
    """Prepare English text for clean speech synthesis."""
    if not text:
        return ""
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'[#*_\(\)\[\]\{\}<>"\']', ' ', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n+', ' ', text)
    return text.strip()

def prepare_audio_script(post_data: Dict[str, Any], lang: str = "fa") -> str:
    """
    Prepare an extensive, natural podcast speech narration script (~2 to 3 minutes).
    Uses the dedicated LLM-authored audio_script when available, or expands
    the article body into a rich spoken technical narrative.
    """
    # 1. Check if high-quality LLM-generated audio_script is already present
    script_candidate = post_data.get("audio_script", "").strip()
    if script_candidate and len(script_candidate) > 120:
        if lang == "fa":
            return clean_persian_tts_script(script_candidate)[:3500]
        else:
            return clean_english_tts_script(script_candidate)[:3500]

    # 2. Comprehensive fallback script generation from content body
    title = post_data.get("title", "").strip()
    description = post_data.get("description", "").strip()
    content_body = post_data.get("content_markdown", "").strip()

    if lang == "fa":
        title_clean = clean_persian_tts_script(title)
        desc_clean = clean_persian_tts_script(description)

        # Extract meaningful body paragraphs (skip code and headers)
        body_paras = []
        for p in content_body.split("\n\n"):
            p_strip = p.strip()
            if not p_strip.startswith(("#", "```", "|", "- ", "1. ", "http")):
                cleaned_p = clean_persian_tts_script(p_strip)
                if len(cleaned_p) > 60:
                    body_paras.append(cleaned_p)
            if len(body_paras) >= 3:
                break

        body_summary = " ".join(body_paras)

        parts = [
            "سلام و درود، به پادکست فنی شیرپلا خوش آمدید.",
            f"در این قسمت، به بررسی و تحلیل گزارش {title_clean} می‌پردازیم.",
            desc_clean,
            body_summary,
            "از کلیدی‌ترین توصیه‌های عملیاتی برای مهندسان زیرساخت، توجه ویژه به پایش مستمر متریک‌ها، تنظیم دقیق منابع و ارتقای تاب‌آوری سیستم است.",
            "از اینکه همراه پادکست شیرپلا بودید سپاسگزاریم."
        ]
        full_script = " ".join([p for p in parts if p]).strip()
        return clean_persian_tts_script(full_script)[:3500]

    else:
        title_clean = clean_english_tts_script(title)
        desc_clean = clean_english_tts_script(description)

        body_paras = []
        for p in content_body.split("\n\n"):
            p_strip = p.strip()
            if not p_strip.startswith(("#", "```", "|", "- ", "1. ", "http")):
                cleaned_p = clean_english_tts_script(p_strip)
                if len(cleaned_p) > 60:
                    body_paras.append(cleaned_p)
            if len(body_paras) >= 3:
                break

        body_summary = " ".join(body_paras)

        parts = [
            "Welcome to the Shirpala technical audio podcast.",
            f"In today's engineering breakdown, we investigate {title_clean}.",
            desc_clean,
            body_summary,
            "Key operational recommendations emphasize hardened boundaries, granular telemetry, and proactive capacity planning.",
            "Thank you for listening to Shirpala."
        ]
        full_script = " ".join([p for p in parts if p]).strip()
        return clean_english_tts_script(full_script)[:3500]

def _split_into_chunks(text: str, max_chunk_chars: int = 180) -> List[str]:
    """Split long text into natural sentence-based chunks to prevent Nexus TTS timeout."""
    if len(text) <= max_chunk_chars:
        return [text]

    chunks = []
    # Split by periods, question marks, or commas
    delimiters = re.split(r'([\.!\?،]+)', text)
    current = ""

    for item in delimiters:
        if not item:
            continue
        if len(current) + len(item) <= max_chunk_chars:
            current += item
        else:
            if current.strip():
                chunks.append(current.strip())
            current = item

    if current.strip():
        chunks.append(current.strip())

    return [c for c in chunks if len(c.strip()) > 3]

def _stitch_wav_buffers(wav_bytes_list: List[bytes]) -> Optional[bytes]:
    """Seamlessly stitch multiple WAV buffers into a single continuous WAV."""
    valid_wavs = [w for w in wav_bytes_list if w and w.startswith(b'RIFF')]
    if not valid_wavs:
        return None
    if len(valid_wavs) == 1:
        return valid_wavs[0]

    out_buf = io.BytesIO()
    try:
        with wave.open(io.BytesIO(valid_wavs[0]), "rb") as w0:
            params = w0.getparams()

        with wave.open(out_buf, "wb") as out_w:
            out_w.setparams(params)
            for wb in valid_wavs:
                try:
                    with wave.open(io.BytesIO(wb), "rb") as w:
                        out_w.writeframes(w.readframes(w.getnframes()))
                except Exception:
                    pass
        return out_buf.getvalue()
    except Exception as e:
        print(f"[AudioTTS] WAV stitching warning: {e}")
        return valid_wavs[0]

def _call_nexus_single_chunk(chunk: str, model: str, voice: str) -> Optional[bytes]:
    """Call Nexus /v1/audio/speech for a single chunk."""
    endpoint = f"{NEXUSLLM_BASE_URL}/audio/speech"
    payload = {
        "model": model,
        "input": chunk,
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
        with opener.open(req, timeout=40) as resp:
            audio_bytes = resp.read()
            if audio_bytes.startswith(b'{"detail"') or audio_bytes.startswith(b'{"error"'):
                return None
            return audio_bytes
    except Exception as e:
        print(f"[AudioTTS] Nexus chunk call error: {e}")
        return None

def _call_nexus_tts_chunked(script: str, model: str, voice: str) -> Optional[bytes]:
    """Call Nexus Piper in sentence chunks to avoid 500 timeouts on long scripts."""
    if not NEXUSLLM_API_KEY:
        return None

    chunks = _split_into_chunks(script, max_chunk_chars=180)
    print(f"[AudioTTS] Processing {len(chunks)} speech chunk(s) via Nexus ({model})...")

    wav_buffers = []
    for idx, chunk in enumerate(chunks, 1):
        wb = _call_nexus_single_chunk(chunk, model, voice)
        if wb:
            wav_buffers.append(wb)
        else:
            print(f"[AudioTTS] Chunk {idx}/{len(chunks)} failed on Nexus.")

    if not wav_buffers:
        return None

    return _stitch_wav_buffers(wav_buffers)

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

def _synthesize_edge_tts(script: str, output_mp3: Path, lang: str = "fa", voice: Optional[str] = None) -> bool:
    """Synthesize speech using Microsoft Azure Neural voices for studio-grade human quality."""
    try:
        import asyncio
        import edge_tts

        if not voice:
            voice = "fa-IR-FaridNeural" if lang == "fa" else "en-US-AndrewMultilingualNeural"

        async def _synthesize():
            comm = edge_tts.Communicate(script, voice)
            await comm.save(str(output_mp3))

        asyncio.run(_synthesize())
        return output_mp3.exists() and output_mp3.stat().st_size > 0
    except Exception as e:
        print(f"[AudioTTS] Edge Neural synthesis warning ({lang}): {e}")
        return False

def generate_post_audio(
    post_data: Dict[str, Any],
    lang: str = "fa",
    output_dir: Path = AUDIO_OUTPUT_DIR
) -> Optional[str]:
    """
    Generate an audio version (MP3) of the post.
    Produces comprehensive ~2-3 minute podcast-style audio narration.
    For Persian:
      - If TTS_VOICE specifies Neural (e.g. fa-IR-FaridNeural) or TTS_PROVIDER=edge: uses studio Neural voice.
      - Default: uses Nexus Piper with sentence chunking + phonetic transliteration, with Neural fallback.
    For English:
      - Uses Andrew Multilingual Neural.
    Returns relative URL path (e.g., /audio/posts/<slug>-<lang>.mp3) or None.
    """
    if not TTS_ENABLED:
        return None

    slug = post_data.get("slug", "post")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_file = output_dir / f"{slug}-{lang}.mp3"

    script = prepare_audio_script(post_data, lang=lang)
    word_count = len(script.split())
    print(f"[AudioTTS] Synthesizing [{lang.upper()}] podcast audio for '{slug}' ({word_count} words)...")

    preferred_voice = os.getenv("TTS_VOICE", TTS_VOICE)
    preferred_provider = os.getenv("TTS_PROVIDER", "nexus").lower()

    if lang == "fa":
        # Check if studio Neural voice is explicitly configured
        if "Farid" in preferred_voice or "Dilara" in preferred_voice or preferred_provider == "edge":
            print(f"[AudioTTS] Using studio Neural voice ({preferred_voice}) for Persian narration...")
            if _synthesize_edge_tts(script, audio_file, lang="fa", voice=preferred_voice):
                size_kb = audio_file.stat().st_size // 1024
                print(f"[AudioTTS] ✅ FA Studio Audio generated: {audio_file.name} ({size_kb} KB)")
                return f"/audio/posts/{slug}-fa.mp3"

        # Priority 1: NexusLLM Piper API with sentence chunking
        audio_bytes = _call_nexus_tts_chunked(script, model=TTS_MODEL, voice=TTS_VOICE)
        if audio_bytes:
            success = _convert_to_mp3(audio_bytes, audio_file)
            if success and audio_file.exists() and audio_file.stat().st_size > 1000:
                size_kb = audio_file.stat().st_size // 1024
                print(f"[AudioTTS] ✅ FA Audio generated via Nexus Piper: {audio_file.name} ({size_kb} KB)")
                return f"/audio/posts/{slug}-fa.mp3"

        # Automatic Fallback: High-Fidelity Neural voice
        print("[AudioTTS] Nexus Piper failed or timed out; falling back to studio FaridNeural voice...")
        if _synthesize_edge_tts(script, audio_file, lang="fa", voice="fa-IR-FaridNeural"):
            size_kb = audio_file.stat().st_size // 1024
            print(f"[AudioTTS] ✅ FA Audio generated via Neural fallback: {audio_file.name} ({size_kb} KB)")
            return f"/audio/posts/{slug}-fa.mp3"

    else:
        # English: High-Fidelity Andrew Neural
        if _synthesize_edge_tts(script, audio_file, lang="en", voice="en-US-AndrewMultilingualNeural"):
            size_kb = audio_file.stat().st_size // 1024
            print(f"[AudioTTS] ✅ EN Audio generated via edge-tts: {audio_file.name} ({size_kb} KB)")
            return f"/audio/posts/{slug}-en.mp3"

        # Fallback for English: Nexus Piper
        audio_bytes = _call_nexus_single_chunk(script[:400], model=TTS_MODEL, voice="en_US-lessac-medium")
        if audio_bytes:
            success = _convert_to_mp3(audio_bytes, audio_file)
            if success and audio_file.exists() and audio_file.stat().st_size > 1000:
                size_kb = audio_file.stat().st_size // 1024
                print(f"[AudioTTS] ✅ EN Audio generated via Nexus: {audio_file.name} ({size_kb} KB)")
                return f"/audio/posts/{slug}-en.mp3"

    print(f"[AudioTTS] ❌ Could not generate audio for '{slug}' ({lang}).")
    return None
