from flask import Flask, render_template, request, redirect, url_for, session
import google.generativeai as genai
import json
import os
import uuid
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# -------------------- Load .env and Configure App --------------------
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_key_123")  # ✅ Should come AFTER app = Flask

# -------------------- Gemini API Configuration --------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("❌ Gemini API key not found in environment variables.")

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# -------------------- File Paths --------------------
USERS_FILE = "users.json"

# -------------------- History Helpers --------------------
def get_history_file():
    if 'user' in session:
        username = session['user']['name'].lower().replace(" ", "_")
        return f"chat_history_{username}.json"
    return "chat_history_guest.json"

def load_history():
    filename = get_history_file()
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            return json.load(f)
    return []

def save_history(history):
    filename = get_history_file()
    with open(filename, 'w') as f:
        json.dump(history, f, indent=4)

# -------------------- User Helpers --------------------
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return []

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# -------------------- Chat Helpers --------------------
def get_chat_by_id(chat_id):
    for chat in load_history():
        if chat['id'] == chat_id:
            return chat
    return None

def create_new_chat():
    chat_id = str(uuid.uuid4())[:8]
    new_chat = {"id": chat_id, "title": "New Chat", "messages": []}
    history = load_history()
    history.append(new_chat)
    save_history(history)
    return chat_id

# -------------------- Auth Routes --------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email'].lower()
        password = request.form['password']

        users = load_users()
        for u in users:
            if u['email'] == email:
                return "⚠️ Email already registered."

        hashed_pw = generate_password_hash(password)
        users.append({'name': name, 'email': email, 'password': hashed_pw})
        save_users(users)

        session['user'] = {'name': name, 'email': email}
        return redirect(url_for('home'))

    return render_template("signup.html")

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']

        users = load_users()
        for user in users:
            if user['email'].lower() == email and check_password_hash(user['password'], password):
                session['user'] = {'name': user['name'], 'email': user['email']}
                return redirect(url_for('home'))

        return "⚠️ Invalid email or password."

    return render_template("login.html")

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

# -------------------- Chat Routes --------------------
@app.route('/')
def home():
    if 'user' not in session:
        return redirect(url_for('signup'))

    history = load_history()
    if history:
        return redirect(url_for('chat', chat_id=history[-1]['id']))
    else:
        chat_id = create_new_chat()
        return redirect(url_for('chat', chat_id=chat_id))

@app.route('/chat/<chat_id>')
def chat(chat_id):
    if 'user' not in session:
        return redirect(url_for('signup'))

    chat_data = get_chat_by_id(chat_id)
    if not chat_data:
        return redirect(url_for('home'))

    return render_template("index.html", current_chat=chat_data, chats=load_history(), username=session['user']['name'])

@app.route('/chat/<chat_id>/send', methods=['POST'])
def send(chat_id):
    if 'user' not in session:
        return redirect(url_for('signup'))

    user_input = request.form['msg']
    try:
        response = model.generate_content(user_input)
        bot_reply = response.text.strip()
    except Exception as e:
        bot_reply = f"⚠️ Error: {str(e)}"

    history = load_history()
    for chat in history:
        if chat['id'] == chat_id:
            chat['messages'].append({"user": user_input, "bot": bot_reply})
            if chat['title'] == "New Chat":
                chat['title'] = user_input[:20] + "..." if len(user_input) > 20 else user_input
            break
    save_history(history)
    return redirect(url_for('chat', chat_id=chat_id))

@app.route('/new')
def new_chat():
    if 'user' not in session:
        return redirect(url_for('signup'))

    chat_id = create_new_chat()
    return redirect(url_for('chat', chat_id=chat_id))

@app.route('/chat/<chat_id>/delete', methods=['POST'])
def delete_chat(chat_id):
    if 'user' not in session:
        return redirect(url_for('signup'))

    history = load_history()
    history = [chat for chat in history if chat['id'] != chat_id]
    save_history(history)

    if history:
        return redirect(url_for('chat', chat_id=history[-1]['id']))
    else:
        return redirect(url_for('home'))

# -------------------- Run Server --------------------
if __name__ == "__main__":
    app.run(debug=True)
