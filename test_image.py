import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("ERROR: GEMINI_API_KEY not found")
    exit()

client = genai.Client(api_key=api_key)

image_path = "uploads/pothole.jpg"

with open(image_path, "rb") as f:
    image_bytes = f.read()

prompt = """
Analyze this civic issue image.

Classify the image into ONE of these categories:
- Pothole
- Garbage
- Broken Streetlight
- Water Leakage
- Other

Then provide:
Issue:
Suggested Priority: Low / Medium / High
Department:
Reason:

Priority is only a suggestion based on visible evidence.
Keep the answer short.
"""

try:
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=[
            prompt,
            types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg"
            )
        ]
    )

    print("\n--- CivicLens AI Analysis ---\n")
    print(response.text)

except Exception as e:
    print("\nAI analysis failed:")
    print(e)