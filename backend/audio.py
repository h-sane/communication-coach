# backend/audio.py
import os
import time
import logging
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Config from env
GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
GROQ_API_URL = os.environ.get("GROQ_API_URL") or os.environ.get("GROQ_API_URL")

# Timeout / retry tuned for demo: small files transcribe quickly
UPLOAD_TIMEOUT = 60  # seconds
POLL_INTERVAL = 1.5  # seconds
POLL_TIMEOUT = 120   # seconds - max wait for transcription

class ASRProviderError(RuntimeError):
    pass

def _assert_provider_config():
    if not GROQ_API_KEY or not GROQ_API_URL:
        raise ASRProviderError("ASR provider not configured. Set GROQ_API_KEY and GROQ_API_URL in environment/secrets.")

def process_audio(file_path: str) -> dict:
    """
    Upload audio file to a remote ASR provider (Groq-like), poll for result,
    then return dict:
      {
        "text": str,
        "segments": [{"start": float, "end": float, "text": str}, ...],
        "duration": float,
        "wpm": int,
        "word_count": int
      }
    """
    _assert_provider_config()

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file not found: {file_path}")

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }

    # 1) Upload the file - many providers accept multipart/form-data POST
    #    Adjust 'file' and params as needed for your provider.
    with open(file_path, "rb") as fh:
        files = {"file": (os.path.basename(file_path), fh, "application/octet-stream")}
        # Required params for Groq API
        data = {
            "model": "whisper-large-v3",
            "response_format": "verbose_json",
            "temperature": 0.0
        }

        logger.info("Uploading audio to ASR provider...")
        try:
            resp = requests.post(GROQ_API_URL, headers=headers, files=files, data=data, timeout=UPLOAD_TIMEOUT)
        except Exception as e:
            logger.exception("Upload failed")
            raise ASRProviderError(f"Upload failed: {e}")

    if not resp.ok:
        logger.error("Upload returned non-200: %s %s", resp.status_code, resp.text)
        raise ASRProviderError(f"Upload failed: {resp.status_code} - {resp.text}")

    # 2) Provider returns either immediate transcription or a job id to poll
    j = resp.json()
    logger.debug("Upload response: %s", j)

    # Try to guess what provider returned. Two common patterns:
    # - Immediate transcription with 'text' and 'segments'
    # - Job object with 'id' and status endpoint / 'result_url'
    # We'll attempt both patterns.

    # Pattern A: immediate result
    if "text" in j and ("segments" in j or "words" in j or "timestamps" in j):
        logger.info("ASR returned immediate transcription")
        return _parse_provider_response(j)

    # Pattern B: job-based
    job_id = j.get("id") or j.get("job_id") or j.get("transcription_id")
    status_url = j.get("status_url") or j.get("result_url") or j.get("url")
    poll_url = None
    if job_id:
        # If provider expects polling at /jobs/{job_id}:
        poll_url = f"{GROQ_API_URL.rstrip('/')}/jobs/{job_id}"
    elif status_url:
        poll_url = status_url

    if not poll_url:
        # Unknown response format: return raw
        logger.error("Unknown response format from ASR provider: %s", j)
        raise ASRProviderError("Unknown ASR provider response. Check GROQ_API_URL and provider docs.")

    logger.info("Polling ASR job at: %s", poll_url)
    start = time.time()
    while True:
        if time.time() - start > POLL_TIMEOUT:
            raise ASRProviderError("Timeout waiting for transcription result.")
        try:
            poll_resp = requests.get(poll_url, headers=headers, timeout=30)
        except Exception as e:
            logger.exception("Polling failed")
            raise ASRProviderError(f"Polling failed: {e}")

        if not poll_resp.ok:
            logger.error("Polling returned non-200: %s %s", poll_resp.status_code, poll_resp.text)
            # If 404/410 temporarily, continue; else break
            if 500 <= poll_resp.status_code < 600:
                time.sleep(POLL_INTERVAL)
                continue
            raise ASRProviderError(f"Polling failed: {poll_resp.status_code} - {poll_resp.text}")

        pj = poll_resp.json()
        logger.debug("Poll response: %s", pj)

        # Status keys commonly: status, state, done, completed
        status = pj.get("status") or pj.get("state") or pj.get("job_status")
        if status and str(status).lower() in ("completed", "done", "succeeded", "finished"):
            # job done — parse result object (may be under 'result' or 'transcription')
            result = pj.get("result") or pj.get("transcription") or pj
            return _parse_provider_response(result)
        elif status and str(status).lower() in ("failed", "error"):
            logger.error("Transcription job failed: %s", pj)
            raise ASRProviderError(f"ASR job failed: {pj}")
        else:
            # Not done yet - sleep then retry
            time.sleep(POLL_INTERVAL)


def _parse_provider_response(resp_json: dict) -> dict:
    """
    Parse provider JSON to the standard output format.
    This is tolerant: it searches for 'text' and a best-effort 'segments' list.
    """
    # full text
    text = resp_json.get("text") or resp_json.get("transcript") or resp_json.get("transcription") or ""
    if isinstance(text, list):
        # some providers return a list of segments for 'text'
        text = " ".join([t.get("text", "") for t in text])

    # Extract segments: try multiple common keys
    segments = []
    if "segments" in resp_json and isinstance(resp_json["segments"], list):
        for s in resp_json["segments"]:
            # support s having start,end,text or t, start_time etc.
            start = _safe_float(s.get("start") or s.get("start_time") or s.get("t0") or 0.0)
            end = _safe_float(s.get("end") or s.get("end_time") or s.get("t1") or start)
            seg_text = s.get("text") or s.get("content") or s.get("token_text") or ""
            segments.append({"start": start, "end": end, "text": seg_text})
    else:
        # try word-level timestamps
        words = resp_json.get("words") or resp_json.get("alternatives") or []
        if isinstance(words, list) and words and isinstance(words[0], dict):
            # coalesce contiguous words into segments roughly by sentence (simple)
            cur_text = []
            cur_start = None
            cur_end = None
            for w in words:
                st = _safe_float(w.get("start") or w.get("start_time"))
                et = _safe_float(w.get("end") or w.get("end_time"))
                token = w.get("text") or w.get("word") or w.get("token") or ""
                if cur_start is None:
                    cur_start = st
                cur_end = et or cur_end
                cur_text.append(token)
                # naive break: when token ends with punctuation or length > 10 words
                if token.endswith((".", "?", "!")) or len(cur_text) >= 10:
                    segments.append({"start": cur_start or 0.0, "end": cur_end or cur_start or 0.0, "text": " ".join(cur_text)})
                    cur_text = []
                    cur_start = None
                    cur_end = None
            # flush remaining
            if cur_text:
                segments.append({"start": cur_start or 0.0, "end": cur_end or cur_start or 0.0, "text": " ".join(cur_text)})

    # Fallback: if no segments, produce one segment with whole text at 0..duration
    duration = 0.0
    if segments:
        try:
            duration = max([s["end"] for s in segments])
        except Exception:
            duration = 0.0
    else:
        # Attempt to get duration from resp_json
        duration = _safe_float(resp_json.get("duration") or resp_json.get("audio_duration") or 0.0)
        if text:
            segments = [{"start": 0.0, "end": duration or 0.0, "text": text}]

    word_count = len(text.split()) if text else 0
    wpm = int(word_count / (duration / 60)) if duration > 0 else 0

    return {
        "text": text,
        "segments": segments,
        "duration": duration,
        "wpm": wpm,
        "word_count": word_count
    }

def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return 0.0
