import assemblyai as aai
from fastapi import UploadFile

class STTService:
    def __init__(self, api_key: str):
        aai.settings.api_key = api_key

    async def transcribe(self, file: UploadFile) -> str:
        audio_bytes = await file.read()
        transcriber = aai.Transcriber()
        transcript = transcriber.transcribe(audio_bytes)
        return transcript.text
