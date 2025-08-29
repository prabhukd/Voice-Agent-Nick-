import assemblyai as aai
from assemblyai.streaming.v3 import (
    BeginEvent, StreamingClient, StreamingClientOptions, StreamingError, StreamingEvents, StreamingParameters, TurnEvent, TerminationEvent
)
import logging
from typing import Type
from fastapi import WebSocket
from config import ASSEMBLY_API_KEY

async def transcribe_stream_ws(websocket: WebSocket):
    await websocket.accept()
    api_key = ASSEMBLY_API_KEY
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    transcript_accum = []
    error_msg = None

    class WSStreamingClient(StreamingClient):
        def on_begin(self, event: BeginEvent):
            logger.info(f"Session started: {event.id}")

        def on_turn(self, event: TurnEvent):
            logger.info(f"Turn: {event.transcript} (end_of_turn={event.end_of_turn})")
            if event.transcript:
                transcript_accum.append(event.transcript)
                import asyncio
                asyncio.create_task(websocket.send_text(event.transcript))

        def on_terminated(self, event: TerminationEvent):
            logger.info(f"Session terminated: {event.audio_duration_seconds} seconds of audio processed")

        def on_error(self, error: StreamingError):
            nonlocal error_msg
            logger.error(f"Error occurred: {error}")
            error_msg = str(error)

    client = WSStreamingClient(
        StreamingClientOptions(api_key=api_key, api_host="streaming.assemblyai.com")
    )
    client.on(StreamingEvents.Begin, client.on_begin)
    client.on(StreamingEvents.Turn, client.on_turn)
    client.on(StreamingEvents.Termination, client.on_terminated)
    client.on(StreamingEvents.Error, client.on_error)

    try:
        client.connect(StreamingParameters(sample_rate=16000, format_turns=False))
        while True:
            audio_chunk = await websocket.receive_bytes()
            client.send_audio(audio_chunk)
    except Exception as e:
        logger.error(f"WebSocket/AssemblyAI error: {e}")
        await websocket.send_text(f"[ERROR] {e}")
    finally:
        client.disconnect(terminate=True)
