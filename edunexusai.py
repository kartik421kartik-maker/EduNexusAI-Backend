import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

app = Flask(__name__)
CORS(app)

# [SYSTEM] Multiple FREE API keys work together as a fallback pool.
# Add GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3
# (and as many as you want) to Render Environment Variables.
# Each separate Google AI Studio project has its own independent
# free daily quota. When one key's quota is exhausted, the code
# automatically tries the next available key.
# If only GEMINI_API_KEY is set, it will still work normally.
_raw_keys = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
]

clients = [genai.Client(api_key=k) for k in _raw_keys if k]

if not clients:
    raise RuntimeError(
        "No GEMINI_API_KEY is set in the Environment Variables!"
    )

# gemini-1.5-flash has been retired -- use an explicit current model.
# Flash-Lite has a separate quota bucket from Flash and is usually
# more generous on the free tier.
MODEL_NAME = "gemini-3.5-flash-lite"

# [SYSTEM] EduNexus AI personality + answer LENGTH is controlled here.
SYSTEM_PROMPT = (
    "You are EduNexus AI, a friendly study assistant for Indian Class 12 students "
    "(Physics, Chemistry, Maths, Computer Science, English). "
    "Keep answers SHORT and clear by default -- around 3 to 6 short sentences, "
    "or a few bullet points. Do not write long essays. "
    "Only give a longer, detailed, step-by-step explanation if the student clearly "
    "asks for it (e.g. 'explain in detail', 'step by step', 'derive it', etc.). "
    "Use simple, exam-friendly language."
)


@app.route('/chat', methods=['POST'])
def chat():
    # Receive the question from the website
    user_message = request.json.get('message')
    print(f"\n[USER QUERY RECEIVED]: {user_message}")

    last_error = None

    for i, client in enumerate(clients, start=1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=user_message,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=600,   # Cap very long responses here
                )
            )

            print(f"[EduNexus AI] Reply sent using key #{i}")
            return jsonify({"reply": response.text})

        except genai_errors.ClientError as e:
            if getattr(e, "code", None) == 429:
                # This key's free quota is exhausted -- try the next key
                print(
                    f"[QUOTA HIT on key #{i}] "
                    "trying next key if available..."
                )
                last_error = e
                continue

            print(f"[ERROR DETAILS]: {e}")
            return jsonify({
                "reply": "Oops! Something went wrong. Please try again later!"
            })

        except Exception as e:
            print(f"[ERROR DETAILS]: {e}")
            return jsonify({
                "reply": "Oops! The AI engine is overloaded. Please try again later!"
            })

    # All keys have exhausted their free daily quota
    print(f"[ALL KEYS EXHAUSTED]: {last_error}")

    return jsonify({
        "reply": "⏳ The AI engine's free limit has been exhausted for today. "
                 "Please try again tomorrow or after some time!"
    })


if __name__ == '__main__':
    print("--------------------------------------------------")
    print("[SYSTEM] EduNexus AI LIVE SERVER BOOTING...")
    print(f"[SYSTEM] {len(clients)} API key(s) loaded in the fallback pool")
    print("[SYSTEM] Ready to receive frontend requests")
    print("--------------------------------------------------")

    # CLOUD FIX: Render requires a dynamic port
    port = int(os.environ.get("PORT", 5000))

    app.run(
        host='0.0.0.0',
        port=port
    )
