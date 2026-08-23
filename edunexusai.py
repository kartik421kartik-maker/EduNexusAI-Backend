import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

app = Flask(__name__)
CORS(app)

# [SYSTEM] Multiple FREE API keys ek "pool" ki tarah kaam karenge.
# Render ke Environment Variables mein GEMINI_API_KEY, GEMINI_API_KEY_2, GEMINI_API_KEY_3
# (jitni bhi bana sako) daal do. Har ALAG Google AI Studio PROJECT ka apna independent
# free daily quota hota hai -- ek key ka quota khatam hote hi, code khud agli try karega.
# Abhi sirf GEMINI_API_KEY set hai toh bhi ye bilkul waisa hi chalega jaisa pehle chal raha tha.
_raw_keys = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
]
clients = [genai.Client(api_key=k) for k in _raw_keys if k]

if not clients:
    raise RuntimeError("Koi bhi GEMINI_API_KEY set nahi hai Environment Variables mein!")

# gemini-1.5-flash retire ho chuka hai -- explicit current model use karo.
# Flash-Lite Flash se ALAG quota bucket hai aur free tier par usually zyada generous hota hai.
MODEL_NAME = "gemini-3.5-flash-lite"

# [SYSTEM] EduNexus AI ki personality + answer LENGTH yahin control hoti hai
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
    # Website se question lena
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
                    max_output_tokens=600,   # bahut lambe jawab ko yahin cap kar do
                )
            )
            print(f"[EduNexus AI] Reply sent using key #{i}")
            return jsonify({"reply": response.text})

        except genai_errors.ClientError as e:
            if getattr(e, "code", None) == 429:
                # Is key ka free daily quota khatam -- agli key try karo (agar hai)
                print(f"[QUOTA HIT on key #{i}] trying next key if available...")
                last_error = e
                continue
            print(f"[ERROR DETAILS]: {e}")
            return jsonify({"reply": "Oops! Kuch gadbad ho gayi. Thodi der baad try karo!"})

        except Exception as e:
            print(f"[ERROR DETAILS]: {e}")
            return jsonify({"reply": "Oops! Engine overload ho gaya. Thodi der baad try karo!"})

    # Sabhi keys ka free daily quota khatam ho chuka hai
    print(f"[ALL KEYS EXHAUSTED]: {last_error}")
    return jsonify({"reply": "⏳ Aaj ke liye AI Engine ka free limit sabhi tarah se khatam ho gaya hai. Kal try karna, ya thodi der baad!"})

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("[SYSTEM] EduNexus AI LIVE SERVER BOOTING...")
    print(f"[SYSTEM] {len(clients)} API key(s) loaded in the fallback pool")
    print("[SYSTEM] Ready to receive frontend requests")
    print("--------------------------------------------------")

    # CLOUD FIX: Render ke liye dynamic port zaroori hai
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
