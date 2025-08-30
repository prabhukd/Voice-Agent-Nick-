import asyncio
import websockets
import json
import base64
import httpx
from fastapi import WebSocket
from config import ASSEMBLY_API_KEY, GEMINI_API_KEY, MURF_API_KEY

# This is a coroutine to stream audio chunks to AssemblyAI and yield transcript events
async def assemblyai_stream(audio_chunk_iter):
    ws_url = f"wss://api.assemblyai.com/v2/realtime/ws?sample_rate=16000"
    headers = {"Authorization": ASSEMBLY_API_KEY}
    async with websockets.connect(ws_url, extra_headers=headers) as ws:
        async def send_audio():
            async for chunk in audio_chunk_iter:
                await ws.send(chunk)
            await ws.send(json.dumps({"terminate_session": True}))
        send_task = asyncio.create_task(send_audio())
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            if data.get("message_type") == "FinalTranscript" or data.get("message_type") == "PartialTranscript":
                yield data
            if data.get("message_type") == "SessionTerminated":
                break
        await send_task

# This is a coroutine to stream text to Gemini and yield text chunks
async def gemini_stream(text):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:streamGenerateContent?key={GEMINI_API_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{"parts": [{"text": text}]}],
        "system_instruction": {"parts": [{"text": "You are a helpful, friendly, conversational voice assistant named Nick."}]}
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            async for line in resp.aiter_lines():
                if line.strip():
                    try:
                        data = json.loads(line)
                        for cand in data.get("candidates", []):
                            chunk = cand.get("content", {}).get("parts", [{}])[0].get("text", "")
                            if chunk:
                                yield chunk
                    except Exception:
                        continue

# This is a coroutine to stream text to Murf and yield audio chunks
async def murf_stream(text):
    ws_url = f"wss://api.murf.ai/v1/speech/stream-input?api-key={MURF_API_KEY}&sample_rate=44100&channel_type=MONO&format=WAV"
    context_id = "streaming-ctx"
    async with websockets.connect(ws_url) as ws:
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
        text_msg = {"context_id": context_id, "text": text, "end": True}
        await ws.send(json.dumps(text_msg))
        while True:
            response = await ws.recv()
            data = json.loads(response)
            if "audio" in data:
                yield base64.b64decode(data["audio"])
            if data.get("final"):
                break

# Main FastAPI WebSocket endpoint
async def voice_agent_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        # 1. Receive audio chunks from frontend and stream to AssemblyAI
        async def audio_iter():
            while True:
                chunk = await websocket.receive_bytes()
                if chunk == b"__END__":
                    break
                yield chunk
        # 2. Get transcript from AssemblyAI
        async for stt_event in assemblyai_stream(audio_iter()):
            transcript = stt_event.get("text") or stt_event.get("transcript")
            if transcript and stt_event.get("message_type") == "FinalTranscript":
                # 3. Stream transcript to Gemini
                async for gemini_chunk in gemini_stream(transcript):
                    await websocket.send_json({"type": "gemini", "text": gemini_chunk})
                    # 4. Stream Gemini chunk to Murf and send audio back
                    async for audio_chunk in murf_stream(gemini_chunk):
                        await websocket.send_bytes(audio_chunk)
    except Exception as e:
        await websocket.send_json({"type": "error", "error": str(e)})
    finally:
        await websocket.close()
