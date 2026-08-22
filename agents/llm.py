import os 
from dotenv import load_dotenv
from google import genai

# This explicitly loads the .env file in the current directory
load_dotenv()

_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.6-flash"

def ask_gemini(prompt: str) -> str:
    response = _client.models.generate_content(
        model=MODEL,
        contents=prompt
    )
    return response.text

if __name__ == "__main__":
    try:
        answer = ask_gemini("Explain redis queues in one sentence.")
        print(answer)
    except Exception as e:
        print(f"Unable to generate output: {e}")