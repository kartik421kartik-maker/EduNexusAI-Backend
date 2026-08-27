import os
import base64
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

clients = [genai.Client(api_key=k) for k in _raw_keys if k]

if not clients:
    raise RuntimeError(
        "No GEMINI_API_KEY is set in the Environment Variables!"
    )

# Model Version
MODEL_NAME = "gemini-3.5-flash-lite"

# [SYSTEM] EduNexus AI personality
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
    # Frontend se data receive karna
    data = request.json
    user_message = data.get('message', '').strip()
    b64_string = data.get('image_data')  # Yeh actually file/image dono handle karega
    file_name = data.get('file_name', 'Attachment')

    print(f"\n[USER QUERY RECEIVED]: {user_message}")
    
    # 🧠 Step 1: AI ke liye contents list taiyaar karna
    contents = []

    # Agar koi photo ya PDF aayi hai, usko decode karke list mein daalo
    if b64_string:
        print(f"[FILE RECEIVED]: {file_name}")
        try:
            # Frontend format bhejta hai: "data:image/jpeg;base64,/9j/4AAQ..."
            # Humein mime_type (image/jpeg ya application/pdf) aur actual data alag karna hai
            mime_type = b64_string.split(';')[0].split(':')[1]
            base64_data = b64_string.split(',')[1]
            raw_bytes = base64.b64decode(base64_data)

            # Gemini ko file bytes ke format mein dena
            contents.append(
                types.Part.from_bytes(data=raw_bytes, mime_type=mime_type)
            )
        except Exception as e:
            print(f"[FILE PARSE ERROR]: {e}")
            return jsonify({"reply": "Oops! File process karne mein error aayi. Ek baar check karna ki file sahi format mein hai ya nahi!"})

    # Agar user ne message likha hai, toh usko bhi list mein jod do
    # Message me jo "[Do NOT use LaTeX...]" wala tag hai wo frontend se automatically aa raha hai
    if user_message:
        contents.append(user_message)

    last_error = None

    # 🚀 Step 2: Gemini API ko Request Bhejna
    for i, client in enumerate(clients, start=1):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,  # Yahan dono image aur text ek sath jayenge
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=600,
                )
            )

            print(f"[EduNexus AI] Reply sent using key #{i}")
            return jsonify({"reply": response.text})

        except genai_errors.ClientError as e:
            if getattr(e, "code", None) == 429:
                # Quota over, fallback to next key
                print(f"[QUOTA HIT on key #{i}] trying next key if available...")
                last_error = e
                continue

            print(f"[ERROR DETAILS]: {e}")
            return jsonify({
                "reply": "Oops! Something went wrong while analyzing the query. Please try again later!"
            })

        except Exception as e:
            print(f"[ERROR DETAILS]: {e}")
            return jsonify({
                "reply": "Oops! The AI engine is currently overloaded. Give it a minute and try again!"
            })

    print(f"[ALL KEYS EXHAUSTED]: {last_error}")
    return jsonify({
        "reply": "⏳ The AI engine's free limit has been exhausted for today. Please try again tomorrow!"
    })

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("[SYSTEM] EduNexus AI LIVE SERVER BOOTING...")
    print(f"[SYSTEM] {len(clients)} API key(s) loaded in the fallback pool")
    print("[SYSTEM] VISION & PDF CAPABILITIES: ONLINE")
    print("--------------------------------------------------")

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
