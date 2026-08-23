import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

app = Flask(__name__)
CORS(app)

# [SYSTEM] Render ke Environment Variables se asli key uthayega
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# [SYSTEM] gemini-1.5-flash retire ho chuka hai -- explicit current model use karo.
# Flash-Lite Flash se ALAG quota bucket hai aur free tier par usually zyada generous
# hota hai, isliye agar plain Flash ka daily limit khatam ho bhi jaaye, ye fresh chalega.
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

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=600,   # extra safety: bahut lambe jawab ko yahin cap kar do
            )
        )
        print("[EduNexus AI] Sent response back to frontend!")
        return jsonify({"reply": response.text})

    except genai_errors.ClientError as e:
        # 429 = free-tier daily/rate limit khatam ho gaya. Student ko raw error-dump
        # dikhane ke bajaye friendly message do; asli detail sirf server logs mein jaaye.
        if getattr(e, "code", None) == 429:
            print(f"[QUOTA HIT]: {e}")
            return jsonify({"reply": "⏳ Abhi AI Engine ka free daily limit khatam ho gaya hai (bahut saare sawaal aa gaye!). Thodi der baad ya kal try karo."})
        print(f"[ERROR DETAILS]: {e}")
        return jsonify({"reply": "Oops! Kuch gadbad ho gayi. Thodi der baad try karo!"})

    except Exception as e:
        # Koi aur unexpected error
        print(f"[ERROR DETAILS]: {e}")
        return jsonify({"reply": "Oops! Engine overload ho gaya. Thodi der baad try karo!"})

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("[SYSTEM] EduNexus AI LIVE SERVER BOOTING...")
    print("[SYSTEM] Ready to receive frontend requests") # Emoji removed for terminal safety
    print("--------------------------------------------------")

    # CLOUD FIX: Render ke liye dynamic port zaroori hai
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
