from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
import os, traceback, time, asyncio, random
from collections import deque

app = FastAPI(title="Yedapo YouTube Transcripts")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.yedapo.com", "https://yedapo.com", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

API_KEY = os.environ.get("API_KEY", "")

# --- Rate Limiting ---
# Track request timestamps to enforce spacing
_request_times = deque(maxlen=100)
MIN_DELAY_SECONDS = 3      # Minimum seconds between requests
MAX_REQUESTS_PER_MINUTE = 8  # Max requests per rolling minute


def _check_rate_limit():
    """Enforce rate limiting to avoid YouTube IP bans."""
    now = time.time()
    
    # Clean old entries (older than 60s)
    while _request_times and now - _request_times[0] > 60:
        _request_times.popleft()
    
    # Check per-minute limit
    if len(_request_times) >= MAX_REQUESTS_PER_MINUTE:
        wait_until = _request_times[0] + 60
        wait_secs = wait_until - now
        if wait_secs > 0:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limited. Try again in {wait_secs:.0f}s",
                headers={"Retry-After": str(int(wait_secs) + 1)},
            )
    
    # Enforce minimum delay between requests
    if _request_times:
        elapsed = now - _request_times[-1]
        if elapsed < MIN_DELAY_SECONDS:
            sleep_time = MIN_DELAY_SECONDS - elapsed + random.uniform(0.5, 2.0)
            time.sleep(sleep_time)
    
    # Add random jitter to look more human
    time.sleep(random.uniform(0.3, 1.5))
    
    _request_times.append(time.time())


@app.get("/health")
def health():
    now = time.time()
    recent = sum(1 for t in _request_times if now - t < 60)
    return {
        "status": "ok",
        "requests_last_minute": recent,
        "rate_limit": MAX_REQUESTS_PER_MINUTE,
    }


@app.get("/transcript/{video_id}")
def get_transcript(
    video_id: str,
    lang: str = Query("en", description="Preferred language code"),
    key: str = Query("", description="API key"),
):
    # Simple API key check
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Enforce rate limiting BEFORE hitting YouTube
    _check_rate_limit()

    # Legacy YouTube language codes
    LEGACY_LANGS = {"he": "iw", "id": "in", "yi": "ji"}

    try:
        ytt = YouTubeTranscriptApi()

        # Build language priority list
        langs_to_try = [lang]
        if lang in LEGACY_LANGS:
            langs_to_try.append(LEGACY_LANGS[lang])
        if lang != "en":
            langs_to_try.append("en")
        for modern, legacy in LEGACY_LANGS.items():
            if modern not in langs_to_try:
                langs_to_try.append(modern)
            if legacy not in langs_to_try:
                langs_to_try.append(legacy)

        last_error = None

        # Method 1: Direct fetch with language preference
        for try_lang in langs_to_try:
            try:
                result = ytt.fetch(video_id, languages=[try_lang])
                text = " ".join(s.text for s in result).strip()
                if text:
                    return {
                        "video_id": video_id,
                        "language": result.language_code,
                        "is_generated": result.is_generated,
                        "text": text,
                        "segments": [
                            {"text": s.text, "start": s.start, "duration": s.duration}
                            for s in result
                        ],
                    }
            except Exception as e:
                last_error = e
                continue

        # Method 2: List all transcripts and pick first available
        try:
            transcript_list = ytt.list(video_id)
            for t in transcript_list:
                result = t.fetch()
                text = " ".join(s.text for s in result).strip()
                if text:
                    return {
                        "video_id": video_id,
                        "language": t.language_code,
                        "is_generated": t.is_generated,
                        "text": text,
                        "segments": [
                            {"text": s.text, "start": s.start, "duration": s.duration}
                            for s in result
                        ],
                    }
        except Exception as e:
            last_error = e

        detail = str(last_error) if last_error else "No transcript found"
        raise HTTPException(status_code=404, detail=detail)

    except HTTPException:
        raise
    except TranscriptsDisabled:
        raise HTTPException(status_code=403, detail="Transcripts disabled for this video")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="Video unavailable")
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail="No transcript found")
    except Exception as e:
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{tb}")
