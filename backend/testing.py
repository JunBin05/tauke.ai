import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ILMU_API_KEY")
model   = os.getenv("ILMU_MODEL", "ilmu-glm-5.1")

print(f"Key loaded: {'YES (' + api_key[:8] + '...)' if api_key else 'NO (None or empty)'}")

response = requests.post(
    "https://api.ilmu.ai/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    },
    json={
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "user", "content": "Say hello."}
        ],
    },
    timeout=15,
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
