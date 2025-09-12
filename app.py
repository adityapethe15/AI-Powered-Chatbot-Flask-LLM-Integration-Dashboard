from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from groq import Groq
from dotenv import load_dotenv
import fitz  # PyMuPDF
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import json
import markdown 

# Imports for new file types
import pytesseract
from PIL import Image
import docx

# ---------------- CONFIG ----------------
load_dotenv()
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("FLASK_SECRET_KEY", "a-super-secret-key")

# Groq client
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# --- Load model names from environment variables ---
GROQ_MODEL_FAST = os.getenv("GROQ_MODEL_FAST", "gemma-7b-it")
GROQ_MODEL_LARGE = os.getenv("GROQ_MODEL_LARGE", "gemma2-9b-it")


# Database config
DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "port": os.getenv("DB_PORT")
}

# --- User Authentication Setup ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()
    if user_data:
        return User(id=user_data[0], username=user_data[1])
    return None

# --- DATABASE HELPER ---
def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- TEXT EXTRACTION HELPERS ---
def extract_text_from_pdf(file_stream):
    text = ""
    with fitz.open(stream=file_stream, filetype="pdf") as doc:
        for page in doc:
            text += page.get_text()
    return text

def extract_text_from_image(file_stream):
    image = Image.open(file_stream)
    return pytesseract.image_to_string(image)

def extract_text_from_docx(file_stream):
    doc = docx.Document(file_stream)
    return "\n".join([para.text for para in doc.paragraphs])

# ---------------- AUTH ROUTES ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, password_hash FROM users WHERE username = %s", (username,))
        user_data = cur.fetchone()
        cur.close()
        conn.close()
        if user_data and check_password_hash(user_data[1], password):
            user = User(id=user_data[0], username=username)
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash("Invalid username or password")
    return render_template("login.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            flash("Username already exists.")
        else:
            hashed_password = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id",
                (username, hashed_password)
            )
            user_id = cur.fetchone()[0]
            conn.commit()
            user = User(id=user_id, username=username)
            login_user(user)
            return redirect(url_for('index'))
        cur.close()
        conn.close()
    return render_template("register.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ---------------- APP ROUTES ----------------
@app.route("/")
@login_required
def index():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
@login_required
def chat():
    try:
        user_message = request.form.get("message")
        conversation_id = request.form.get("conversation_id")
        file = request.files.get("file")

        if conversation_id in (None, "", "null", "undefined"):
            conversation_id = None
        else:
            try:
                conversation_id = int(conversation_id)
            except ValueError:
                conversation_id = None

        bot_response = "Sorry, something went wrong."
        conn = get_db_connection()
        cur = conn.cursor()

        if conversation_id is None:
            title_source = user_message or (file.filename if file else "Untitled Conversation")
            title = title_source[:30]
            cur.execute(
                "INSERT INTO conversations (title, user_id) VALUES (%s, %s) RETURNING id",
                (title, current_user.id)
            )
            conversation_id = cur.fetchone()[0]
        else:
            cur.execute("SELECT id FROM conversations WHERE id = %s AND user_id = %s", (conversation_id, current_user.id))
            if not cur.fetchone():
                return jsonify({"error": "Unauthorized"}), 403

        cur.execute("SELECT sender, message FROM chat_history WHERE conversation_id = %s ORDER BY id ASC", (conversation_id,))
        rows = cur.fetchall()

        messages = [{"role": "system", "content": "You are a helpful AI assistant."}]
        for sender, message in rows:
            role = "user" if sender == "user" else "assistant"
            messages.append({"role": role, "content": message})

        file_text = ""
        if file:
            filename = file.filename.lower()
            file_stream = file.read()
            if filename.endswith('.pdf'):
                file_text = extract_text_from_pdf(file_stream)
            elif filename.endswith(('.png', '.jpg', '.jpeg')):
                file_text = extract_text_from_image(file_stream)
            elif filename.endswith('.docx'):
                file_text = extract_text_from_docx(file_stream)
            
            prompt_content = f"Use the following document text to answer my questions:\n\n---\n{file_text[:4000]}\n---\n\n{user_message or ''}"
            messages.append({"role": "user", "content": prompt_content})
        elif user_message:
            messages.append({"role": "user", "content": user_message})

        if len(messages) > 1:
            completion = groq_client.chat.completions.create(
                messages=messages, 
                model=GROQ_MODEL_FAST
            )
            bot_response = completion.choices[0].message.content

        if user_message or file:
            cur.execute("INSERT INTO chat_history (conversation_id, sender, message) VALUES (%s, %s, %s)",
                (conversation_id, "user", user_message or f"File uploaded: {file.filename}"))
        cur.execute("INSERT INTO chat_history (conversation_id, sender, message) VALUES (%s, %s, %s)",
            (conversation_id, "bot", bot_response))

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"response": bot_response, "conversation_id": conversation_id})

    except Exception as e:
        import traceback
        print("🔥 ERROR in /chat route:", traceback.format_exc())
        return jsonify({"error": str(e)}), 500

@app.route("/get_conversations", methods=["GET"])
@login_required
def get_conversations():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, title FROM conversations WHERE user_id = %s ORDER BY created_at DESC", (current_user.id,))
    conversations = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(conversations)

@app.route("/get_chat/<int:conversation_id>", methods=["GET"])
@login_required
def get_chat(conversation_id):
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id FROM conversations WHERE id = %s AND user_id = %s", (conversation_id, current_user.id))
    if not cur.fetchone():
        return jsonify({"error": "Unauthorized"}), 403
    cur.execute("SELECT sender, message FROM chat_history WHERE conversation_id = %s ORDER BY created_at ASC", (conversation_id,))
    messages = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(messages)
    
@app.route("/delete_conversation/<int:conversation_id>", methods=["DELETE"])
@login_required
def delete_conversation(conversation_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM conversations WHERE id = %s AND user_id = %s", (conversation_id, current_user.id))
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "Conversation not found or unauthorized"}), 404
            
        cur.close()
        conn.close()
        return jsonify({"success": True, "message": "Conversation deleted."})
    except Exception as e:
        print(f"Error deleting conversation: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, name, progress FROM subjects WHERE user_id = %s ORDER BY name", (current_user.id,))
    subjects = cur.fetchall()
    cur.close()
    conn.close()
    return render_template("dashboard.html", subjects=subjects)

@app.route("/upload_syllabus", methods=["POST"])
@login_required
def upload_syllabus():
    if 'syllabus_file' not in request.files:
        flash("No file part")
        return redirect(url_for('dashboard'))
    file = request.files['syllabus_file']
    if file.filename == '':
        flash("No selected file")
        return redirect(url_for('dashboard'))
    if file and file.filename.endswith('.pdf'):
        try:
            filename = secure_filename(file.filename)
            pdf_text = extract_text_from_pdf(file.read())
            
            parsing_prompt = f"""Parse the following syllabus text into a structured JSON object. The JSON should have a single key "subjects", which is an array of objects. Each object should have two keys: "name" (the subject name) and "topics" (an array of strings, where each string is a topic or unit). Syllabus Text: --- {pdf_text[:4000]} --- """
            completion = groq_client.chat.completions.create(
                messages=[{"role": "system", "content": "You are a JSON parsing expert."}, {"role": "user", "content": parsing_prompt}],
                model=GROQ_MODEL_FAST,
                response_format={"type": "json_object"}
            )
            parsed_data = json.loads(completion.choices[0].message.content)
            
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO syllabuses (user_id, filename, parsed_content) VALUES (%s, %s, %s) RETURNING id",
                (current_user.id, filename, json.dumps(parsed_data)))
            syllabus_id = cur.fetchone()[0]
            for subject_data in parsed_data.get("subjects", []):
                cur.execute("INSERT INTO subjects (syllabus_id, user_id, name) VALUES (%s, %s, %s) RETURNING id",
                    (syllabus_id, current_user.id, subject_data.get("name")))
                subject_id = cur.fetchone()[0]
                for topic_name in subject_data.get("topics", []):
                    cur.execute("INSERT INTO topics (subject_id, name) VALUES (%s, %s)", (subject_id, topic_name))
            conn.commit()
            cur.close()
            conn.close()
            flash("Syllabus uploaded and processed successfully!")
        except Exception as e:
            flash(f"An error occurred: {str(e)}")
            print(f"Syllabus Upload Error: {e}")
        return redirect(url_for('dashboard'))
    else:
        flash("Invalid file type. Please upload a PDF.")
        return redirect(url_for('dashboard'))

@app.route("/view_notes/<int:subject_id>")
@login_required
def view_notes(subject_id):
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, name FROM subjects WHERE id = %s AND user_id = %s", (subject_id, current_user.id))
        subject = cur.fetchone()

        if not subject:
            flash("Subject not found.")
            return redirect(url_for('dashboard'))

        cur.execute("SELECT name FROM topics WHERE subject_id = %s", (subject_id,))
        topics_rows = cur.fetchall()
        topic_names = [row['name'] for row in topics_rows]
        topics_str = ", ".join(topic_names)
        cur.close()
        conn.close()

        # NEW, ADVANCED PROMPT WITH DIAGRAM INSTRUCTIONS
        notes_prompt = f"""
        Act as a master technical writer and educator, combining the detailed, example-rich style of GeeksForGeeks and Javatpoint.
        Your mission is to create a **deeply comprehensive and easily understandable** study guide on the subject of '{subject['name']}', focusing on the following topics: **{topics_str}**.

        For each topic, you must provide the following in a clear, topic-wise structure:
        1.  **In-Depth Explanation:** Elaborate on the core concepts. Use simple analogies and clear, step-by-step explanations to demystify complex ideas.
        2.  **Illustrative Examples:** Provide well-commented code snippets (if applicable) or practical, real-world examples to demonstrate the topic's application.
        3.  **Diagrams and Visuals (using Mermaid JS):** Where a concept can be better explained with a diagram (e.g., flowcharts, architecture, data structures, hierarchies), **generate the diagram using Mermaid.js syntax**. Enclose the Mermaid code in a markdown code block with the language identifier 'mermaid'. For example:
            ```mermaid
            graph TD;
                A-->B;
                A-->C;
                B-->D;
                C-->D;
            ```
        4.  **Key Summary Points:** Conclude each topic with a bulleted list of the most critical takeaways.

        The final output must be a single, cohesive document in Markdown, beginning with an introduction and ending with a final summary. The tone must be authoritative yet accessible.
        """

        completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are an expert tutor who creates excellent, detailed study materials with diagrams."},
                {"role": "user", "content": notes_prompt}
            ],
            model=GROQ_MODEL_LARGE
        )
        
        notes_markdown = completion.choices[0].message.content
        notes_html = markdown.markdown(notes_markdown, extensions=['fenced_code'])

        return render_template("notes.html", subject=subject, notes_html=notes_html, notes_markdown=notes_markdown)

    except Exception as e:
        flash(f"Could not generate study notes at this time. Error: {str(e)}")
        print(f"Notes Generation Error: {e}")
        return redirect(url_for('dashboard'))

@app.route("/generate_quiz/<int:subject_id>", methods=["GET", "POST"])
@login_required
def generate_quiz(subject_id):
    if request.method == "GET":
        flash("Please generate notes before taking a quiz.")
        return redirect(url_for('dashboard'))
        
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, name FROM subjects WHERE id = %s AND user_id = %s", (subject_id, current_user.id))
        subject = cur.fetchone()
        cur.close()
        conn.close()

        if not subject:
            flash("Subject not found.")
            return redirect(url_for('dashboard'))
            
        notes_text = request.form.get('notes_text')
        if not notes_text:
            flash("Notes were not provided for quiz generation.")
            return redirect(url_for('view_notes', subject_id=subject.id))

        mcq_prompt = f"""
        Based **ONLY** on the following study notes, generate 10 multiple-choice questions.
        Each question must be directly answerable from the provided text.
        Ensure options are plausible but only one is correct according to the notes.

        --- STUDY NOTES START ---
        {notes_text}
        --- STUDY NOTES END ---

        Provide the output as a single, clean JSON object with one key: "mcqs".
        The value of "mcqs" must be an array of 10 question objects.
        Each question object must have three keys:
        1. "question": A string with the question text.
        2. "options": An array of 4 unique strings as possible answers.
        3. "answer": A string that is an exact match to the correct option.
        """

        completion = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a quiz generator that creates questions strictly from the provided text."},
                {"role": "user", "content": mcq_prompt}
            ],
            model=GROQ_MODEL_FAST,
            response_format={"type": "json_object"}
        )

        mcq_data = json.loads(completion.choices[0].message.content)
        
        return render_template("quiz.html", subject=subject, mcqs=mcq_data.get("mcqs", []))

    except Exception as e:
        flash(f"Could not generate a quiz at this time. Error: {str(e)}")
        print(f"Quiz Generation Error: {e}")
        return redirect(url_for('dashboard'))

@app.route("/submit_quiz/<int:subject_id>", methods=["POST"])
@login_required
def submit_quiz(subject_id):
    try:
        user_answers = request.form
        correct_answers = {key.replace('correct_answer_', ''): value for key, value in user_answers.items() if key.startswith('correct_answer_')}
        
        score = 0
        total_questions = len(correct_answers)
        
        for index, correct_answer in correct_answers.items():
            user_answer = user_answers.get(f"question_{index}")
            if user_answer == correct_answer:
                score += 1
        
        quiz_percentage = (score / total_questions) * 100 if total_questions > 0 else 0

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT progress FROM subjects WHERE id = %s AND user_id = %s", (subject_id, current_user.id))
        current_progress_result = cur.fetchone()

        if current_progress_result is None:
            flash("Subject not found.")
            cur.close()
            conn.close()
            return redirect(url_for('dashboard'))

        current_progress = current_progress_result[0]
        new_progress = min(100, round((current_progress + quiz_percentage) / 2))
        
        cur.execute("UPDATE subjects SET progress = %s WHERE id = %s", (new_progress, subject_id))
        
        conn.commit()
        cur.close()
        conn.close()

        flash(f"Quiz submitted! You scored {score}/{total_questions}. Your progress has been updated to {new_progress}%.")
        return redirect(url_for('dashboard'))

    except Exception as e:
        flash(f"An error occurred while submitting your quiz: {str(e)}")
        print(f"Quiz Submission Error: {e}")
        return redirect(url_for('dashboard'))

@app.route("/clear_subjects", methods=['POST'])
@login_required
def clear_subjects():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT id FROM subjects WHERE user_id = %s", (current_user.id,))
        subject_ids = [item[0] for item in cur.fetchall()]
        if subject_ids:
            cur.execute("DELETE FROM topics WHERE subject_id = ANY(%s)", (subject_ids,))
            cur.execute("DELETE FROM subjects WHERE user_id = %s", (current_user.id,))
        conn.commit()
        cur.close()
        conn.close()
        flash("All subjects have been cleared successfully.")
    except Exception as e:
        flash(f"An error occurred: {str(e)}")
        print(f"Clear Subjects Error: {e}")
    return redirect(url_for('dashboard'))

if __name__ == "__main__":
    app.run(debug=True)