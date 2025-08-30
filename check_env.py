import os
from dotenv import load_dotenv

ENV_PATH = ".env"

PLACEHOLDER_KEYS = {
    "ASSEMBLYAI_API_KEY": "your_assemblyai_api_key_here",
    "MURF_API_KEY": "your_murf_api_key_here",
    "GEMINI_API_KEY": "your_gemini_api_key_here"
}

# ✅ Ensure .env exists with placeholder keys
if not os.path.exists(ENV_PATH):
    with open(ENV_PATH, "w") as f:
        for key, value in PLACEHOLDER_KEYS.items():
            f.write(f"{key}={value}\n")
    print(f"✅ Created {ENV_PATH} with placeholder API keys.")

# ✅ Load keys from .env
load_dotenv(ENV_PATH)

missing = []
for key, placeholder in PLACEHOLDER_KEYS.items():
    value = os.getenv(key)
    if value is None or value == placeholder:
        missing.append(key)

if missing:
    print(f"⚠️ WARNING: The following API keys are missing or placeholders: {', '.join(missing)}. Please set real values in {ENV_PATH}.")
else:
    print("✅ All API keys successfully loaded from .env")
