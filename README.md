# Yedapo YouTube Transcripts Service

Lightweight FastAPI microservice that fetches YouTube video transcripts.

## API

```
GET /transcript/{video_id}?lang=en&key=YOUR_KEY
```

Response:
```json
{
  "video_id": "epZy_NajGnA",
  "language": "en",
  "is_generated": false,
  "text": "full transcript text...",
  "segments": [{"text": "...", "start": 0.0, "duration": 1.5}]
}
```

## Deploy to Railway

1. Fork this repo
2. Go to [railway.app](https://railway.app)
3. New Project → Deploy from GitHub
4. Set env var: `API_KEY=your_secret_key`
5. Done — Railway auto-deploys on push

## Environment Variables

| Var | Required | Description |
|-----|----------|-------------|
| `API_KEY` | Optional | Protect the endpoint |
| `PORT` | Auto | Set by Railway |
