# WebSocket streaming voice agent endpoint

from fastapi import FastAPI, File, UploadFile, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from services.voice_stream_ws import voice_agent_ws

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.websocket("/ws/voice")
async def ws_voice(websocket: WebSocket):
    await voice_agent_ws(websocket)

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/process-audio/{session_id}")
async def process_audio_endpoint(session_id: str, file: UploadFile = File(...)):
    audio_bytes = await file.read()
    result = await process_audio(audio_bytes, session_id)
    # ...existing code...
    return result

# Streaming Murf TTS endpoint
@app.get("/stream-murf-tts/{session_id}")
async def stream_murf_tts(session_id: str, text: str):
    # Streams audio chunks as soon as they are received from Murf
    return StreamingResponse(murf_tts_streamer(text), media_type="audio/wav")

# Streaming chat endpoint: streams Gemini text, then Murf TTS audio as soon as available
@app.post("/stream-chat/{session_id}")
async def stream_chat(session_id: str, file: UploadFile = File(...)):
    audio_bytes = await file.read()
    # 1. Transcribe audio (AssemblyAI, blocking)
    transcript = None
    headers = {"authorization": ASSEMBLY_API_KEY, "content-type": "application/octet-stream"}
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            upload_resp = await client.post("https://api.assemblyai.com/v2/upload", headers=headers, content=audio_bytes)
            upload_resp.raise_for_status()
            audio_url = upload_resp.json()["upload_url"]
            transcribe_resp = await client.post(
                "https://api.assemblyai.com/v2/transcript",
                headers=headers,
                json={"audio_url": audio_url}
            )
            transcribe_resp.raise_for_status()
            transcript_id = transcribe_resp.json()["id"]
            while True:
                poll = await client.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers)
                poll.raise_for_status()
                status = poll.json()["status"]
                if status == "completed":
                    transcript = poll.json()["text"]
                    break
                elif status == "failed":
                    yield b"event: error\ndata: Transcription failed.\n\n"
                    return
                await asyncio.sleep(2)
    except Exception as e:
        yield f"event: error\ndata: Transcription error: {e}\n\n".encode()
        return

    if not transcript or not transcript.strip():
        yield b"event: error\ndata: I couldn't hear you. Please speak louder or check your microphone.\n\n"
        return

    # 2. Update chat history
    if session_id not in chat_histories:
        chat_histories[session_id] = []
    chat_histories[session_id].append({"role": "user", "text": transcript})

    # 3. Stream Gemini response (text)
    gemini_context = []
    if len(chat_histories[session_id]) >= 2:
        prev_bot = chat_histories[session_id][-2]
        if prev_bot["role"] == "bot":
            gemini_context.append({"role": "model", "parts": [{"text": prev_bot["text"]}]})
    gemini_context.append({"role": "user", "parts": [{"text": chat_histories[session_id][-1]["text"]}]})
    try:
        gemini_text = await call_gemini(gemini_context)
    except Exception as e:
        yield f"event: error\ndata: Gemini error: {e}\n\n".encode()
        return
    if not gemini_text or not isinstance(gemini_text, str) or not gemini_text.strip():
        gemini_text = "Sorry, I couldn't generate a response right now."
    chat_histories[session_id].append({"role": "bot", "text": gemini_text})
    # Send Gemini text as soon as available
    yield f"event: gemini\ndata: {gemini_text}\n\n".encode()

    # 4. Stream Murf TTS audio as soon as available
    try:
        async for chunk in murf_tts_streamer(gemini_text):
            # Send each chunk as base64-encoded WAV
            import base64
            b64 = base64.b64encode(chunk).decode()
            yield f"event: audio\ndata: {b64}\n\n".encode()
    except Exception as e:
        yield f"event: error\ndata: Murf TTS error: {e}\n\n".encode()
        return






# ...existing code...


# ...existing code...

# Tavily search skill integration
from tavily import TavilyClient
tavily_client = TavilyClient(api_key="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")

# WeatherAPI.com integration
import re
import requests

WEATHER_API_KEY = "3a8a9e9977484fa89ef142525252608"

def get_weather(city: str):
    url = f"http://api.weatherapi.com/v1/current.json?key={WEATHER_API_KEY}&q={city}"
    try:
        resp = requests.get(url)
        if resp.status_code == 200:
            data = resp.json()
            location = data['location']['name'] + ', ' + data['location']['country']
            temp = data['current']['temp_c']
            feels = data['current']['feelslike_c']
            desc = data['current']['condition']['text']
            return f"The weather in {location} is {desc} with a temperature of {temp}°C (feels like {feels}°C)."
        else:
            return "Sorry, I couldn't get the weather for that location."
    except Exception as e:
        return "Sorry, I couldn't get the weather right now."
import sys
import os
import shutil
import asyncio
import httpx
import base64

from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect
import websockets
import json


# API Keys (imported from config.py)
from config import GEMINI_API_KEY, MURF_API_KEY, ASSEMBLY_API_KEY

# Chat histories store
chat_histories = {}

# ======================
# Gemini API call
# ======================
async def call_gemini(prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    # If prompt is a string, wrap it as a single message; if it's a list, use as context
    if isinstance(prompt, str):
        contents = [{"parts": [{"text": prompt}]}]
    else:
        contents = prompt
    payload = {
        "contents": contents,
        "system_instruction": {"parts": [{"text": "You are a human. Your name is Nick. You are a helpful, friendly, and conversational voice assistant. If someone greets you by name (Nick), respond warmly as Nick."}]}
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            candidates = data.get("candidates", [])
            if candidates:
                return candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            return "[No Gemini response]"
    except Exception as e:
        print("Gemini error:", e)
        return "[Error contacting Gemini]"


# ======================
# Murf TTS API call (returns base64 audio)
# ======================
from fastapi.responses import StreamingResponse
import uuid

async def murf_tts_streamer(text: str):
    import websockets
    import json
    ws_url = f"wss://api.murf.ai/v1/speech/stream-input?api-key={MURF_API_KEY}&sample_rate=44100&channel_type=MONO&format=WAV"
    context_id = str(uuid.uuid4())
    try:
        async with websockets.connect(ws_url) as ws:
            # Send voice config (optional, can be customized)
            voice_config_msg = {
                "voice_config": {
                    "voiceId": "en-IN-aarav",
                    "style": "Conversational",
                    "rate": 0,
                    "pitch": 0,
                    "variation": 1
                }
            }
            await ws.send(json.dumps(voice_config_msg))
            # Send text with context_id
            text_msg = {"context_id": context_id, "text": text, "end": True}
            await ws.send(json.dumps(text_msg))
            while True:
                response = await ws.recv()
                data = json.loads(response)
                if "audio" in data:
                    # Stream each audio chunk as soon as received (base64-encoded WAV)
                    yield base64.b64decode(data["audio"])
                if data.get("final"):
                    break
    except Exception as e:
        print("Murf TTS WebSocket error:", e)
        return

# ======================
# Process Audio Pipeline
# ======================
async def process_audio(audio_bytes: bytes, session_id: str):
    headers = {"authorization": ASSEMBLY_API_KEY, "content-type": "application/octet-stream"}
    transcript = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Upload
            upload_resp = await client.post("https://api.assemblyai.com/v2/upload", headers=headers, content=audio_bytes)
            upload_resp.raise_for_status()
            audio_url = upload_resp.json()["upload_url"]
            # Transcribe
            transcribe_resp = await client.post(
                "https://api.assemblyai.com/v2/transcript",
                headers=headers,
                json={"audio_url": audio_url}
            )
            transcribe_resp.raise_for_status()
            transcript_id = transcribe_resp.json()["id"]

            # Poll for completion
            while True:
                poll = await client.get(f"https://api.assemblyai.com/v2/transcript/{transcript_id}", headers=headers)
                poll.raise_for_status()
                status = poll.json()["status"]
                if status == "completed":
                    transcript = poll.json()["text"]
                    break
                elif status == "failed":
                    return {"text": "", "gemini": None, "audio_base64": None, "history": [], "error": "Transcription failed."}
                await asyncio.sleep(2)
    except httpx.ReadTimeout:
        return {"text": "", "gemini": None, "audio_base64": None, "history": [], "error": "Transcription service timed out. Please try again or check your network connection."}
    except Exception as e:
        print("AssemblyAI error:", e)
        return {"text": "", "gemini": None, "audio_base64": None, "history": [], "error": f"Transcription service error: {e}"}


    if not transcript or not transcript.strip():
        gemini_text = "I couldn't hear you. Please speak louder or check your microphone."
        if session_id not in chat_histories:
            chat_histories[session_id] = []
        chat_histories[session_id].append({"role": "bot", "text": gemini_text})
        return {
            "text": "",
            "gemini": gemini_text,
            "audio_base64": None,
            "history": chat_histories[session_id],
        }

    # Always append user message to chat_histories before Gemini
    if session_id not in chat_histories:
        chat_histories[session_id] = []
    chat_histories[session_id].append({"role": "user", "text": transcript})


    # Build Gemini context: previous bot response (if any) and latest user message
    gemini_context = []
    if len(chat_histories[session_id]) >= 2:
        prev_bot = chat_histories[session_id][-2]
        if prev_bot["role"] == "bot":
            gemini_context.append({"role": "model", "parts": [{"text": prev_bot["text"]}]})
    gemini_context.append({"role": "user", "parts": [{"text": chat_histories[session_id][-1]["text"]}]})

    # Gemini response with minimal context
    try:
        gemini_text = await call_gemini(gemini_context)
    except Exception as e:
        print(f"[process_audio] Gemini error: {e}")
        gemini_text = "Sorry, I couldn't generate a response right now."
    if not gemini_text or not isinstance(gemini_text, str) or not gemini_text.strip():
        gemini_text = "Sorry, I couldn't generate a response right now."
    chat_histories[session_id].append({"role": "bot", "text": gemini_text})
    print(f"[process_audio] Gemini response: {gemini_text}")

    # Murf response (TTS, base64 audio)
    try:
        audio_base64 = await call_murf_tts(gemini_text)
    except Exception as e:
        print(f"[process_audio] Murf TTS error: {e}")
        audio_base64 = None
    if not audio_base64 or not isinstance(audio_base64, str) or not audio_base64.strip():
        print("[process_audio] Murf TTS returned no audio.")
        audio_base64 = None

    return {
        "text": transcript,
        "gemini": gemini_text,
        "audio_base64": audio_base64,
        "history": chat_histories[session_id],
    }

# Helper for backward compatibility: collect all audio chunks and return as base64 string
async def call_murf_tts(text: str) -> str:
    # Always return WAV as base64 (no conversion, no pydub)
    chunks = []
    async for chunk in murf_tts_streamer(text):
        chunks.append(chunk)
    wav_bytes = b"".join(chunks)
    return base64.b64encode(wav_bytes).decode("utf-8")

    if not transcript or not transcript.strip():
        gemini_text = "I couldn't hear you. Please speak louder or check your microphone."
        chat_histories[session_id].append({"role": "bot", "text": gemini_text})
        print(f"Nick: {gemini_text}")
        return {
            "text": transcript,
            "gemini": gemini_text,
            "audio_base64": None,
            "history": chat_histories[session_id],
        }

    # Build Gemini context: only latest user message and previous bot response (if any)
    gemini_context = []
    if len(chat_histories[session_id]) >= 2:
        # Add previous bot response
        prev_bot = chat_histories[session_id][-2]
        if prev_bot["role"] == "bot":
            gemini_context.append({"role": "model", "parts": [{"text": prev_bot["text"]}]})
    # Add latest user message
    gemini_context.append({"role": "user", "parts": [{"text": chat_histories[session_id][-1]["text"]}]})

    # Gemini response with minimal context
    gemini_text = await call_gemini(gemini_context)
    chat_histories[session_id].append({"role": "bot", "text": gemini_text})
    print(f"Nick: {gemini_text}")

    # Murf response (TTS, base64 audio)
    audio_base64 = await call_murf_tts(gemini_text)
    return {
        "text": transcript,
        "gemini": gemini_text,
        "audio_base64": audio_base64,
        "history": chat_histories[session_id],
    }

# ======================
# FastAPI app
# FastAPI app
# ======================

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse("static/index.html")

@app.post("/process-audio/{session_id}")
async def process_audio_endpoint(session_id: str, file: UploadFile = File(...)):
    audio_bytes = await file.read()
    result = await process_audio(audio_bytes, session_id)
    # ...existing code...
    return result

# Streaming Murf TTS endpoint
@app.get("/stream-murf-tts/{session_id}")
async def stream_murf_tts(session_id: str, text: str):
    # Streams audio chunks as soon as they are received from Murf
    return StreamingResponse(murf_tts_streamer(text), media_type="audio/wav")