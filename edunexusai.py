import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

app = Flask(__name__)
CORS(app)

# [SYSTEM] Multiple FREE API keys fallback pool
_raw_keys = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
]

# Create clients only for the keys that actually exist in Render
clients = [genai.Client(api_key=k) for k in _raw_keys if k]

if not clients:
    raise RuntimeError(
        "No GEMINI_API_KEY is set in the Environment Variables!"
    )

# Claude ke suggestion wala model jisne limit error theek kiya
MODEL_NAME = "gemini-3.5-flash-lite"

# [SYSTEM] Smart Prompt: Short by default, LONG only when asked!
# [SYSTEM] Smart & Natural AI Prompt
SYSTEM_PROMPT = (
    "You are EduNexus AI, an expert study assistant for Indian Class 12 students "
    "(Physics, Chemistry, Maths, Computer Science, English). "
    "Adapt your response length and style NATURALLY based on the user's query: "
    "1. For concepts, definitions, or general questions: Provide a simple explanation followed by 1 or 2 practical examples. Keep it concise. "
    "2. For sample papers, mock tests, or full derivations: Provide the COMPLETE and detailed response immediately. "
    "CRITICAL RULE: If a user asks for a sample paper or questions, DO NOT give a blueprint, structure, or outline. "
    "DO NOT ask for permission like 'Let me know if you want the actual questions'. "
    "YOU MUST GENERATE THE FULL LIST OF ACTUAL QUESTIONS IMMEDIATELY."
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
                    max_output_tokens=2500,  # 🚀 BADA DABBA: Ab sample paper beech me nahi tootega!
                )
            )

            print(f"[EduNexus AI] Reply sent using key #{i}")
            return jsonify({"reply": response.text})

        except genai_errors.ClientError as e:
            if getattr(e, "code", None) == 429:
                # Limit cross ho gayi, agli key try karo
                print(f"[QUOTA HIT on key #{i}] trying next key if available...")
                last_error = e
                continue

            # Koi aur client error
            print(f"[ERROR DETAILS]: {e}")
            return jsonify({
                "reply": "Oops! Something went wrong with the connection. Please try again! ✦"
            })

        except Exception as e:
            # Server crash ya timeout
            print(f"[ERROR DETAILS]: {e}")
            return jsonify({
                "reply": "Whoops! The AI engine is experiencing high traffic right now. Please try again in a few seconds! ✦"
            })

    # Agar saari keys ki daily limit khatam ho jaye
    print(f"[ALL KEYS EXHAUSTED]: {last_error}")
    return jsonify({
        "reply": "⏳ The AI engine's free limit has been exhausted for today. Please try again tomorrow or after some time! ✦"
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
