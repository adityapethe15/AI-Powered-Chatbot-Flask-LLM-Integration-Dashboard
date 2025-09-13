# AI-Powered Chatbot with LLM Integration & Study Dashboard

This is a full-stack web application built with Python and Flask that integrates a powerful AI chatbot using the Groq LLM API. The application features a comprehensive study dashboard that allows users to parse syllabuses, generate notes, create quizzes, and track their learning progress.

---
## ✨ Key Features

### 💬 AI Chat Functionality
- **LLM Integration:** Real-time, responsive chat powered by the Groq API.
- **Document Analysis:** Users can upload PDF, DOCX, and image files for the AI to analyze and answer questions about.
- **Conversation History:** All conversations are saved, allowing users to review, continue, or delete them.

### 🎓 Study Dashboard
- **Syllabus Parsing:** Automatically extracts subjects and topics from an uploaded PDF syllabus.
- **Note Generation:** Generates detailed study notes for any subject using an AI model.
- **Quiz Generation:** Creates multiple-choice quizzes based on the generated notes to test user knowledge.
- **Progress Tracking:** A visual dashboard displays learning progress for each subject.

### 💻 General Features
- **User Authentication:** Secure user registration and login system.
- **Responsive Design:** The UI is optimized for both desktop and mobile devices.
- **Theme Support:** Includes a toggle for light and dark mode.
- **Voice Input:** Supports voice-to-text for hands-free interaction with the chatbot.

---
## 🚀 Usage Workflow

1.  **Authentication:** A user creates an account or logs in.
2.  **Syllabus Upload:** On the dashboard, the user uploads a PDF syllabus. The system parses it into subjects.
3.  **Note Generation:** The user selects a subject to generate detailed study notes.
4.  **Quiz Practice:** After reviewing the notes, the user can generate a quiz to test their knowledge. Progress is updated on the dashboard.
5.  **General Chat:** At any time, the user can interact with the AI chatbot, including uploading documents for context.

---
## 🛠️ Technology Stack

- **Backend:** Python, Flask
- **Database:** PostgreSQL
- **AI / LLM:** Groq API
- **Frontend:** HTML, CSS, JavaScript
- **Frameworks:** Bootstrap 5

---
## ⚙️ Local Installation

1.  **Clone the project:**
    ```bash
    git clone [https://github.com/adityapethe15/AI-Powered-Chatbot-Flask-LLM-Integration-Dashboard.git](https://github.com/adityapethe15/AI-Powered-Chatbot-Flask-LLM-Integration-Dashboard.git)
    cd AI-Powered-Chatbot-Flask-LLM-Integration-Dashboard
    ```

2.  **Set up a virtual environment and install dependencies:**
    ```bash
    # Create and activate the environment
    python -m venv venv && source venv/bin/activate
    # Install required packages
    pip install -r requirements.txt
    ```

3.  **Create your `.env` file:**
    Create a new file named `.env` in the root directory. Fill it with your secret keys and database URL:
    ```ini
    FLASK_SECRET_KEY="your_secret_key"
    GROQ_API_KEY="your_groq_api_key"
    DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DATABASE_NAME"
    ```

4.  **Run the application:**
    ```bash
    flask run
    ```
    The application will be accessible at `https://study-assistance-chatbot.onrender.com`.