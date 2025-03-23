from flask import Flask, request, jsonify, render_template, url_for, session
from flask_bcrypt import Bcrypt
import pytesseract
from PIL import Image
import whisper
from transformers import pipeline
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Change this for security
bcrypt = Bcrypt(app)

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        email TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL
                    )''')
    conn.commit()
    conn.close()

init_db()

# Load the pre-trained BERT model
try:
    bert_classifier = pipeline("text-classification", model="jy46604790/Fake-News-Bert-Detect")
except Exception as e:
    print(f" Error loading BERT model: {e}")
    bert_classifier = None

# Load Whisper model
try:
    whisper_model = whisper.load_model("base")
except Exception as e:
    print(f" Error loading Whisper model: {e}")
    whisper_model = None

# Extract text from image
def extract_text_from_image(image):
    try:
        return pytesseract.image_to_string(Image.open(image)).strip()
    except Exception as e:
        return f"Error extracting text from image: {str(e)}"

# Extract speech from video
def extract_text_from_video(video_path):
    try:
        result = whisper_model.transcribe(video_path)
        return result["text"].strip()
    except Exception as e:
        return f"Error extracting text from video: {str(e)}"

# User Registration
@app.route("/register", methods=["POST"])
def register():
    data = request.form
    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    
    if not name or not email or not password:
        return jsonify({"error": "All fields are required"}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")
    
    try:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, hashed_password))
        conn.commit()
        conn.close()
        return jsonify({"message": "User registered successfully!"})
    except sqlite3.IntegrityError:
        return jsonify({"error": "Email already registered"}), 400

# User Login
@app.route("/login", methods=["POST"])
def login():
    data = request.form
    email = data.get("email")
    password = data.get("password")

    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()

    if user and bcrypt.check_password_hash(user[3], password):
        session["user_id"] = user[0]
        session["name"] = user[1]
        return jsonify({"message": "Login successful!", "name": user[1]})
    else:
        return jsonify({"error": "Invalid email or password"}), 401

# User Logout
@app.route("/logout", methods=["POST"])
def logout():
    session.pop("user_id", None)
    session.pop("name", None)
    return jsonify({"message": "Logged out successfully!"})

# Fetch User Profile
# Fetch User Profile
@app.route("/profile", methods=["GET"])
def profile():
    if "user_id" in session:
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name, email FROM users WHERE id = ?", (session["user_id"],))
        user = cursor.fetchone()
        conn.close()

        if user:
            return jsonify({"name": user[0], "email": user[1]})
    
    return jsonify({"error": "User not logged in"}), 401

# Home Route
@app.route('/')
def index():
    return render_template('index.html')

# Fake News Page Route
@app.route("/FakeNews")
def fake_news_page():
    return render_template("FakeNews.html")

# News Checking Route
@app.route('/check_news', methods=['POST'])
def check_news():
    if "user_id" not in session:
        return jsonify({"error": "User not logged in"}), 401

    try:
        text = request.form.get("news_text", "").strip()
        if not text:
            return jsonify({"error": "No text input provided"}), 400

        if not bert_classifier:
            return jsonify({"error": "BERT model failed to load"}), 500

        result = bert_classifier(text)[0]
        label_map = {"LABEL_1": "REAL", "LABEL_0": "FAKE"}
        label = label_map.get(result["label"], "UNKNOWN")
        confidence = round(result["score"] * 100, 2)

        # **Session मध्ये previous checks add करणे**
        if "news_checks" not in session:
            session["news_checks"] = []

        session["news_checks"].insert(0, {  # नवीन check वरती add होईल
            "text": text,
            "result": label,
            "confidence": confidence
        })
        session.modified = True  # **Session update करणे mandatory आहे**

        return jsonify({"result": label, "confidence": confidence})
    
    except Exception as e:
        return jsonify({"error": "Internal Server Error", "details": str(e)}), 500


@app.route("/recent_checks", methods=["GET"])
def recent_checks():
    return jsonify(session.get("news_checks", []))  # Returns stored checks




if __name__ == '__main__':
    app.run(debug=False)
