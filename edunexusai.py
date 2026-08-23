import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai

app = Flask(__name__)
CORS(app)

# [SYSTEM] Render ke Environment Variables se asli key uthayega
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

@app.route('/chat', methods=['POST'])
def chat():
    user_message = request.json.get('message')
    print(f"\n[USER QUERY RECEIVED]: {user_message}")
    
    try:
        # AI se jawab mangna
        response = client.models.generate_content(
            model='gemini-3.6-flash',
            contents=user_message
        )
        answer = response.text
        print("[EduNexus AI] Sent response back to frontend!")
        return jsonify({"reply": answer})
        
   except Exception as e:
        print(f"[ERROR]: {str(e)}")
        friendly_error = "Whoops! The AI engine is experiencing high traffic right now. Please try again in a few seconds! ✦"
        return jsonify({"reply": friendly_error})
if __name__ == '__main__':
    print("--------------------------------------------------")
    print("[SYSTEM] EduNexus AI LIVE SERVER BOOTING...")
    print("[SYSTEM] Ready to receive frontend requests") # Emoji removed for terminal safety
    print("--------------------------------------------------")
    
    # CLOUD FIX: Render ke liye dynamic port zaroori hai
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
