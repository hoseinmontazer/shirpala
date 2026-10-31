import urllib.request
import urllib.error
import mimetypes
import json
import uuid
from pathlib import Path
from typing import Optional
from .config import NEXUSLLM_BASE_URL, NEXUSLLM_API_KEY, WHISPER_MODEL

def transcribe_audio_file(
    file_path: Path,
    model: str = WHISPER_MODEL,
    language: Optional[str] = None
) -> Optional[str]:
    """
    Transcribe an audio file using Whisper on NexusLLM (/v1/audio/transcriptions).
    """
    if not NEXUSLLM_API_KEY:
        print("[Transcriber] NEXUSLLM_API_KEY not set.")
        return None

    if not file_path.exists():
        print(f"[Transcriber] Audio file does not exist: {file_path}")
        return None

    boundary = f"----WebKitFormBoundary{uuid.uuid4().hex}"
    endpoint = f"{NEXUSLLM_BASE_URL}/audio/transcriptions"

    # Build multipart/form-data payload
    body = bytearray()
    
    # model field
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="model"\r\n\r\n'.encode("utf-8"))
    body.extend(f"{model}\r\n".encode("utf-8"))

    # language field (optional)
    if language:
        body.extend(f"--{boundary}\r\n".encode("utf-8"))
        body.extend(f'Content-Disposition: form-data; name="language"\r\n\r\n'.encode("utf-8"))
        body.extend(f"{language}\r\n".encode("utf-8"))

    # file field
    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "audio/mpeg"
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode("utf-8")
    )
    body.extend(f"Content-Type: {mime_type}\r\n\r\n".encode("utf-8"))
    with open(file_path, "rb") as f:
        body.extend(f.read())
    body.extend(b"\r\n")

    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "Authorization": f"Bearer {NEXUSLLM_API_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}"
        }
    )

    try:
        print(f"[Transcriber] Sending audio to {endpoint} with model {model}...")
        with urllib.request.urlopen(req, timeout=120) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            return res_data.get("text", "")
    except Exception as e:
        print(f"[Transcriber] Audio transcription failed: {e}")
        return None

