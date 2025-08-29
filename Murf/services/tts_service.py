from murf import Murf

class TTSService:
    def __init__(self, api_key: str, voice_id: str = "en-IN-aarav"):
        self.client = Murf(api_key=api_key)
        self.voice_id = voice_id

    def synthesize(self, text: str) -> str:
        res = self.client.text_to_speech.generate(text=text, voice_id=self.voice_id)
        return getattr(res, "audio_file", None)
