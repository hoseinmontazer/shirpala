import os
import re
import io
import time
import wave
import json
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.error
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, Optional, List
from .config import (
    NEXUSLLM_BASE_URL,
    NEXUSLLM_API_KEY,
    TTS_ENABLED,
    TTS_MODEL,
    TTS_FALLBACK_MODEL,
    TTS_VOICE,
    TTS_VOICE_PIPER,
    TTS_VOICE_EN,
    TTS_VOICE_EN_PIPER,
    TTS_PROVIDER,
    AUDIO_OUTPUT_DIR,
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
    script_candidate = post_data.get("audio_script", "").strip()
    if script_candidate and len(script_candidate) > 120:
        if lang == "fa":
            return clean_persian_tts_script(script_candidate)[:8000]
        return clean_english_tts_script(script_candidate)[:8000]

    title = post_data.get("title", "").strip()
    description = post_data.get("description", "").strip()
    content_body = post_data.get("content_markdown", "").strip()

    if lang == "fa":
        title_clean = clean_persian_tts_script(title)
        desc_clean = clean_persian_tts_script(description)

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
            "سلام و درود، به پادکاست فنی نولی خوش آمدید.",
            f"در این اپیزود، به بررسی و تحلیل گزارش {title_clean} می‌پردازیم.",
            desc_clean,
            body_summary,
            "از کلیدی‌ترین توصیه‌های عملیاتی برای مهندسان زیرساخت، توجه ویژه به پایش مستمر متریک‌ها، تنظیم دقیق منابع و ارتقای تاب‌آوری سیستم است.",
            "از اینکه همراه پادکاست فنی نولی در وب‌سایت بلاگ نولی بودید سپاسگزاریم.",
        ]
        full_script = " ".join([p for p in parts if p]).strip()
        return clean_persian_tts_script(full_script)[:8000]

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
        "Welcome to the Knowly technical audio podcast.",
        f"In today's engineering breakdown, we investigate {title_clean}.",
        desc_clean,
        body_summary,
        "Key operational recommendations emphasize hardened boundaries, granular telemetry, and proactive capacity planning.",
        "Thank you for listening to Knowly at blog.knowly.ir.",
    ]
    full_script = " ".join([p for p in parts if p]).strip()
    return clean_english_tts_script(full_script)[:8000]


def _split_into_chunks(text: str, max_chunk_chars: int = 180) -> List[str]:
    """Split long text into natural sentence-based chunks to prevent Nexus TTS timeout."""
    if len(text) <= max_chunk_chars:
        return [text]

    chunks = []
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
    valid_wavs = [w for w in wav_bytes_list if w and w.startswith(b"RIFF")]
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


def _is_audio_bytes(data: bytes) -> bool:
    if not data or len(data) < 100:
        return False
    if data[:1] in (b"{", b"[") or data.startswith((b'{"', b'{"detail"', b'{"error"')):
        return False
    return (
        data.startswith(b"RIFF")
        or data.startswith(b"ID3")
        or data.startswith(b"\xff\xfb")
        or data.startswith(b"\xff\xf3")
        or data.startswith(b"\xff\xf2")
        or data[4:8] == b"ftyp"
        or b"LAME" in data[:200]
        or b"Xing" in data[:200]
    )


def _nexus_voice_for_model(model: str, lang: str = "fa") -> str:
    """Pick a voice id compatible with the selected Nexus speech model."""
    model_l = (model or "").lower()
    if "fish" in model_l:
        # Edge Neural voice names are invalid for fish-speech.
        if TTS_VOICE and ("Farid" in TTS_VOICE or "Dilara" in TTS_VOICE or "Neural" in TTS_VOICE):
            return "default"
        return TTS_VOICE or "default"
    if lang == "en":
        return TTS_VOICE_EN_PIPER
    if TTS_VOICE and ("fa_IR" in TTS_VOICE or "amir" in TTS_VOICE.lower()):
        return TTS_VOICE
    return TTS_VOICE_PIPER


def _call_nexus_single_chunk(
    chunk: str,
    model: str,
    voice: str,
    response_format: Optional[str] = None,
    timeout: Optional[int] = None,
) -> Optional[bytes]:
    """Call Nexus /v1/audio/speech for a single chunk (piper WAV or fish-speech MP3)."""
    endpoint = f"{NEXUSLLM_BASE_URL}/audio/speech"
    payload: Dict[str, Any] = {
        "model": model,
        "input": chunk,
        "voice": voice or "default",
    }
    if response_format:
        payload["response_format"] = response_format
    elif "fish" in (model or "").lower():
        payload["response_format"] = "mp3"

    # fish-speech can hang when the manual container is unhealthy; fail fast to piper.
    if timeout is None:
        timeout = 25 if "fish" in (model or "").lower() else 45

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {NEXUSLLM_API_KEY}",
            "Content-Type": "application/json",
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:
            audio_bytes = resp.read()
            if not _is_audio_bytes(audio_bytes):
                preview = audio_bytes[:180].decode("utf-8", errors="replace")
                print(f"[AudioTTS] Nexus non-audio response ({model}): {preview}")
                return None
            return audio_bytes
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read()[:240].decode("utf-8", errors="replace")
        except Exception:
            pass
        print(f"[AudioTTS] Nexus HTTP {e.code} ({model}): {body}")
        return None
    except Exception as e:
        print(f"[AudioTTS] Nexus chunk call error ({model}): {e}")
        return None


def _call_nexus_tts_chunked(script: str, model: str, voice: str) -> Optional[bytes]:
    """
    Call Nexus TTS in sentence chunks.
    fish-speech handles longer chunks; piper needs short ones to avoid timeouts.
    """
    if not NEXUSLLM_API_KEY:
        return None

    is_fish = "fish" in (model or "").lower()
    max_chars = 420 if is_fish else 180
    chunks = _split_into_chunks(script, max_chunk_chars=max_chars)
    print(f"[AudioTTS] Processing {len(chunks)} speech chunk(s) via Nexus ({model}, voice={voice})...")

    audio_buffers: List[Optional[bytes]] = [None] * len(chunks)

    def _fetch_chunk(idx: int, ch: str):
        wb = _call_nexus_single_chunk(ch, model, voice)
        # Retry once for piper; fish-speech already uses a short timeout so skip slow double-wait.
        if not wb and not is_fish:
            time.sleep(0.4)
            wb = _call_nexus_single_chunk(ch, model, voice)
        return idx, wb

    workers = 1 if is_fish else 3
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_fetch_chunk, i, ch) for i, ch in enumerate(chunks)]
        for fut in concurrent.futures.as_completed(futures):
            idx, wb = fut.result()
            if wb:
                audio_buffers[idx] = wb
            else:
                print(f"[AudioTTS] Warning: Chunk {idx + 1}/{len(chunks)} failed on Nexus ({model}).")

    valid = [w for w in audio_buffers if w is not None]
    if not valid:
        return None

    if all(w.startswith(b"RIFF") for w in valid):
        return _stitch_wav_buffers(valid)
    if len(valid) == 1:
        return valid[0]
    return b"".join(valid)


def _convert_to_mp3(raw_bytes: bytes, output_mp3: Path) -> bool:
    """Save audio bytes as MP3, converting with ffmpeg when source is WAV."""
    ffmpeg_bin = shutil.which("ffmpeg")
    is_wav = raw_bytes.startswith(b"RIFF")

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
            str(output_mp3),
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return res.returncode == 0
    finally:
        try:
            os.remove(tmp_wav_path)
        except OSError:
            pass


def _nexus_model_chain() -> List[str]:
    """Ordered Nexus speech models: preferred → fallback → piper safety net."""
    chain: List[str] = []
    for model in (TTS_MODEL, TTS_FALLBACK_MODEL, "piper"):
        if model and model not in chain:
            chain.append(model)
    return chain


def _synthesize_edge_tts(script: str, output_mp3: Path, lang: str = "fa", voice: Optional[str] = None) -> bool:
    """Synthesize speech using Microsoft Azure Neural voices for studio-grade human quality."""
    try:
        import asyncio
        import edge_tts

        if not voice:
            voice = "fa-IR-FaridNeural" if lang == "fa" else TTS_VOICE_EN

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
    output_dir: Path = AUDIO_OUTPUT_DIR,
) -> Optional[str]:
    """
    Generate an audio version (MP3) of the post.

    Persian default (production Nexus):
      1) fish-speech (better Persian pronunciation when healthy)
      2) piper (fa_IR-amir-medium)
      3) edge FaridNeural fallback

    Set TTS_PROVIDER=edge to force studio Neural voices.
    """
    if not TTS_ENABLED:
        return None

    slug = post_data.get("slug", "post")
    output_dir.mkdir(parents=True, exist_ok=True)
    audio_file = output_dir / f"{slug}-{lang}.mp3"

    script = prepare_audio_script(post_data, lang=lang)
    word_count = len(script.split())
    print(f"[AudioTTS] Synthesizing [{lang.upper()}] podcast audio for '{slug}' ({word_count} words)...")

    preferred_provider = os.getenv("TTS_PROVIDER", TTS_PROVIDER).lower()
    preferred_voice = os.getenv("TTS_VOICE", TTS_VOICE)

    if lang == "fa":
        force_edge = preferred_provider == "edge" or "Farid" in preferred_voice or "Dilara" in preferred_voice

        if force_edge:
            edge_voice = preferred_voice if ("Farid" in preferred_voice or "Dilara" in preferred_voice) else "fa-IR-FaridNeural"
            print(f"[AudioTTS] Using studio Neural voice ({edge_voice}) for Persian narration...")
            if _synthesize_edge_tts(script, audio_file, lang="fa", voice=edge_voice):
                size_kb = audio_file.stat().st_size // 1024
                print(f"[AudioTTS] FA Studio Audio generated: {audio_file.name} ({size_kb} KB)")
                return f"/audio/posts/{slug}-fa.mp3"

        for model in _nexus_model_chain():
            voice = _nexus_voice_for_model(model, lang="fa")
            print(f"[AudioTTS] Trying Nexus model={model} voice={voice} ...")
            audio_bytes = _call_nexus_tts_chunked(script, model=model, voice=voice)
            if not audio_bytes:
                continue
            success = _convert_to_mp3(audio_bytes, audio_file)
            if success and audio_file.exists() and audio_file.stat().st_size > 1000:
                size_kb = audio_file.stat().st_size // 1024
                print(f"[AudioTTS] FA Audio generated via Nexus/{model}: {audio_file.name} ({size_kb} KB)")
                return f"/audio/posts/{slug}-fa.mp3"

        print("[AudioTTS] Nexus speech models failed; falling back to studio FaridNeural voice...")
        if _synthesize_edge_tts(script, audio_file, lang="fa", voice="fa-IR-FaridNeural"):
            size_kb = audio_file.stat().st_size // 1024
            print(f"[AudioTTS] FA Audio generated via Neural fallback: {audio_file.name} ({size_kb} KB)")
            return f"/audio/posts/{slug}-fa.mp3"

    else:
        if _synthesize_edge_tts(script, audio_file, lang="en", voice=TTS_VOICE_EN):
            size_kb = audio_file.stat().st_size // 1024
            print(f"[AudioTTS] EN Audio generated via edge-tts: {audio_file.name} ({size_kb} KB)")
            return f"/audio/posts/{slug}-en.mp3"

        for model in _nexus_model_chain():
            voice = _nexus_voice_for_model(model, lang="en")
            audio_bytes = _call_nexus_single_chunk(script[:500], model=model, voice=voice)
            if not audio_bytes:
                continue
            success = _convert_to_mp3(audio_bytes, audio_file)
            if success and audio_file.exists() and audio_file.stat().st_size > 1000:
                size_kb = audio_file.stat().st_size // 1024
                print(f"[AudioTTS] EN Audio generated via Nexus/{model}: {audio_file.name} ({size_kb} KB)")
                return f"/audio/posts/{slug}-en.mp3"

    print(f"[AudioTTS] Could not generate audio for '{slug}' ({lang}).")
    return None
