import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types

app = Flask(__name__)
CORS(app)

# [SYSTEM] Render ke Environment Variables se asli key uthayega
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

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
        # AI se jawab mangna (Cloud par 1.5-flash hi chalta hai)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=user_message,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=600,   # extra safety: bahut lambe jawab ko yahin cap kar do
            )
        )
        print("[EduNexus AI] Sent response back to frontend!")
        return jsonify({"reply": response.text})

    except Exception as e:
        # Agar error aayi toh exact reason website par dikhega
        print(f"[ERROR DETAILS]: {e}")
        return jsonify({"reply": f"Oops! Engine overload ho gaya. Error: {e}"})

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("[SYSTEM] EduNexus AI LIVE SERVER BOOTING...")
    print("[SYSTEM] Ready to receive frontend requests") # Emoji removed for terminal safety
    print("--------------------------------------------------")

    # CLOUD FIX: Render ke liye dynamic port zaroori hai
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
