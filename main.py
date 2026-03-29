from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
import os, traceback

app = FastAPI(title="Yedapo YouTube Transcripts")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.yedapo.com", "https://yedapo.com", "http://localhost:3000"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

API_KEY = os.environ.get("API_KEY", "")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/transcript/{video_id}")
def get_transcript(
    video_id: str,
    lang: str = Query("en", description="Preferred language code"),
    key: str = Query("", description="API key"),
):
    # Simple API key check
    if API_KEY and key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Legacy YouTube language codes (YouTube uses old ISO codes for some languages)
    LEGACY_LANGS = {"he": "iw", "id": "in", "yi": "ji"}

    try:
        ytt = YouTubeTranscriptApi()

        # Try fetching with preferred language first, including legacy variants
        langs_to_try = [lang]
        if lang in LEGACY_LANGS:
            langs_to_try.append(LEGACY_LANGS[lang])
        if lang != "en":
            langs_to_try.append("en")
        # Always try common legacy codes
        for modern, legacy in LEGACY_LANGS.items():
            if modern not in langs_to_try:
                langs_to_try.append(modern)
            if legacy not in langs_to_try:
                langs_to_try.append(legacy)

        transcript = None
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
            transcript_list = ytt.list_transcripts(video_id)
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
