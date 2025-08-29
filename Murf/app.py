from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import os, requests

app = FastAPI()

# Serve static files (CSS + JS) at /static
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve index.html on root
@app.get("/")
async def get():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

# WebSocket for audio streaming
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            print(f"Received {len(data)} bytes of audio")
            # here you would forward chunks to AssemblyAI
    except WebSocketDisconnect:
        print("WebSocket disconnected")


# 🔊 New endpoint for Murf TTS
MURF_API_KEY = "ap2_cd712df0-ee7d-4848-9eeb-d8a8ab3627a8"

@app.post("/tts")
async def tts(request: Request):
    body = await request.json()
    text = body.get("text", "")

    murf_resp = requests.post(
        "https://api.murf.ai/v1/speech/generate",
        headers={"Authorization": f"Bearer {MURF_API_KEY}"},
        json={
            "voiceId": "en-US-wavenet-d",  # pick a voice supported by Murf
            "text": text,
            "format": "mp3"
        }
    )

    if murf_resp.status_code != 200:
        return {"error": "Murf TTS failed"}

    return StreamingResponse(
        iter([murf_resp.content]),
        media_type="audio/mpeg"
    )     