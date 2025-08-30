import google.generativeai as genai

class LLMService:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel("gemini-2.5-flash")

    def get_response(self, messages: list) -> str:
        from google.generativeai.types import GenerateContentConfig, ThinkingConfig
        config = GenerateContentConfig(thinking_config=ThinkingConfig(thinking_budget=0))
        llm_response = self.client.generate_content(messages, config=config)
        llm_text = getattr(llm_response, "text", None)
        return llm_text or str(llm_response)
