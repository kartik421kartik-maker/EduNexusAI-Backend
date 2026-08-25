import os
import requests
import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

app = Flask(__name__)
CORS(app)

# [SYSTEM] Hide Webhook in Backend for Security
DISCORD_WEBHOOK_URL = "https://discordapp.com/api/webhooks/1540079598224809984/oDDtB_T22-8lQK3R1HLTk_L_1Fv6IW-atoHBjo7zq0Wc4BQpVr6Hor2ssAtH7RxXP_fA"

_raw_keys = [
    os.environ.get("GEMINI_API_KEY"),
    os.environ.get("GEMINI_API_KEY_2"),
    os.environ.get("GEMINI_API_KEY_3"),
]

clients = [genai.Client(api_key=k) for k in _raw_keys if k]

if not clients:
    print("WARNING: Koi GEMINI_API_KEY set nahi hai!")

# 🔥 FIX 1: Tu aur Claude sahi the! 1.5 retire ho chuka hai. 3.5-flash-lite is the correct 2026 model!
MODEL_NAME = "gemini-3.5-flash-lite"

SYSTEM_PROMPT = (
    "You are EduNexus AI, powered by the KX Neural Core, a friendly and extremely smart study assistant for Indian Class 12 students "
    "(Physics, Chemistry, Maths, Computer Science, English). "
    "Keep answers SHORT and clear by default -- around 3 to 6 short sentences, "
    "or a few bullet points. Do not write long essays. "
    "If the student requests a custom quiz, act as a strict examiner: provide only "
    "the requested questions and options first, wait for their answers, then mark them "
    "and give them a score. Use simple, exam-friendly language."
)

# [SYSTEM] KX Core Conversation Memory Store
conversation_history = {}

def send_discord_alert(username):
    try:
        data = {"content": f"🚨 **BINGO!** New User Logged In!\n🧑‍🎓 **Name:** {username}\n💻 **Action:** Launched EduNexus AI Dashboard 🚀"}
        requests.post(DISCORD_WEBHOOK_URL, json=data, timeout=5)
    except Exception as e:
        print(f"Discord Alert Failed: {e}")

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        user_message = data.get('message')
        session_id = data.get('session_id', 'default_session')
        user_name = data.get('user_name', 'Student')
        
        print(f"\n[USER QUERY RECEIVED from {user_name}]: {user_message}")

        if session_id not in conversation_history:
            send_discord_alert(user_name)
            # Memory Start with User (Strict Google Rule)
            conversation_history[session_id] = [
                types.Content(role="user", parts=[types.Part.from_text(text=f"My name is {user_name}. Please remember it.")]),
                types.Content(role="model", parts=[types.Part.from_text(text=f"Hello {user_name}, I am KX Neural Core. I will remember your name and our conversation history.")])
            ]

        # Sawaal Memory mein jodo
        conversation_history[session_id].append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )
        
        # Memory Trim karo (Sirf last 10 yaad rakho taaki API rate limit na aaye)
        if len(conversation_history[session_id]) > 10:
            conversation_history[session_id] = conversation_history[session_id][-10:]
            if conversation_history[session_id][0].role == "model":
                conversation_history[session_id] = conversation_history[session_id][1:]

        last_error = None

        for i, client in enumerate(clients, start=1):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=conversation_history[session_id],
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        max_output_tokens=600,
                    )
                )

                ai_response_text = response.text if response.text else "I could not process that request."
                
                # Jawab Memory mein jodo
                conversation_history[session_id].append(
                    types.Content(role="model", parts=[types.Part.from_text(text=ai_response_text)])
                )
                
                print(f"[KX Neural Core] Reply sent using key #{i}")
                return jsonify({"reply": ai_response_text})

            except genai_errors.ClientError as e:
                if getattr(e, "code", None) == 429:
                    print(f"[QUOTA HIT on key #{i}] trying next key if available...")
                    last_error = e
                    continue
                
                print(f"[CLIENT ERROR DETAILS]: {e}")
                return jsonify({"reply": f"API Error: {str(e)}"})

            except Exception as e:
                print(f"[SERVER ERROR DETAILS]: {e}")
                return jsonify({"reply": f"Server Error: {str(e)}"})

        print(f"[ALL KEYS EXHAUSTED]: {last_error}")
        return jsonify({
            "reply": "⏳ Aaj ke liye AI Engine ka free limit khatam ho gaya hai. Kal try karna!"
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({"reply": f"Backend Crash: {str(e)}"}), 200

if __name__ == '__main__':
    print("--------------------------------------------------")
    print("[SYSTEM] KX Neural Core LIVE SERVER BOOTING...")
    print(f"[SYSTEM] Selected Model: {MODEL_NAME}")
    print("--------------------------------------------------")
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
