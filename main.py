from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
    VideoUnavailable,
)
import os

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

    try:
        ytt = YouTubeTranscriptApi()
        transcript_list = ytt.list_transcripts(video_id)

        # Try requested language first, then any available
        transcript = None
        try:
            transcript = transcript_list.find_transcript([lang])
        except NoTranscriptFound:
            pass

        # Try English if not already requested
        if not transcript and lang != "en":
            try:
                transcript = transcript_list.find_transcript(["en"])
            except NoTranscriptFound:
                pass

        # Fall back to first available (manual or generated)
        if not transcript:
            for t in transcript_list:
                transcript = t
                break

        if not transcript:
            raise HTTPException(status_code=404, detail="No transcript found")

        snippets = transcript.fetch()
        text = " ".join(s.text for s in snippets).strip()
        
        return {
            "video_id": video_id,
            "language": transcript.language_code,
            "is_generated": transcript.is_generated,
            "text": text,
            "segments": [
                {"text": s.text, "start": s.start, "duration": s.duration}
                for s in snippets
            ],
        }

    except TranscriptsDisabled:
        raise HTTPException(status_code=403, detail="Transcripts disabled for this video")
    except VideoUnavailable:
        raise HTTPException(status_code=404, detail="Video unavailable")
    except NoTranscriptFound:
        raise HTTPException(status_code=404, detail="No transcript found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
