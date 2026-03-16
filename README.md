# 🧠 AI Quiz Generator (FastAPI + Gemini)

This project is an AI-driven platform that transforms PDF documents into interactive learning tools. Using **Google Gemini AI**, the application parses documents, stores them in a structured database, and generates grade-specific quizzes.

---

## 🛠 Tech Stack

- **Backend:** FastAPI, Uvicorn
    
- **AI Integration:** Google GenAI (Gemini)
    
- **Database:** SQLAlchemy (SQLite/PostgreSQL)
    
- **PDF Processing:** PyPDF
    
- **Templating:** Jinja2
    
- **Frontend:** HTML/Form-data (via `python-multipart`)
    

---

## ⚙️ Installation & Setup

### 1. Install Dependencies

Ensure you have Python 3.8+ installed, then run:

Bash

```
pip install jinja2 fastapi uvicorn google-genai python-multipart sqlalchemy pypdf
```

### 2. Configure Environment Variables

You must set your Gemini API Key to enable AI generation.

**Linux / macOS:**

Bash

```
export GEMINI_API_KEY="AIzaSyBWdTUWC"
```

**Windows (PowerShell):**

Bash

```
$env:GEMINI_API_KEY="AIzaSyBWdTUWC"
```

---

## 🚀 Running the Application

Start the development server with:

Bash

```
uvicorn main:app --reload
```

The application will be live at `http://127.0.0.1:8000`.

---

## 📊 Database Schema

The application uses the following relational structure to manage content and quiz generation:

### Core Tables

- **`documents`**: Stores the source `src_id` and `doc_url` (with a unique index on the URL).
    
- **`chunks`**: Contains segments of text from the PDF, mapped to a `src_id` and categorized by `topic`, `subject`, and `grade`.
    
- **`questions`**: Stores AI-generated questions (`TEXT`), `options` (`JSON`), the correct `answer`, and `difficulty`.
    
- **`users`**: Stores user information including `name` and `user_id`.
    

### Relationships

- **Chunks → Documents**: Each chunk references a parent document via `src_id`.
    
- **Questions → Chunks**: Each question is linked to the specific text segment it was derived from via `src_chunk_id`.
    

---

## 🗺 API Endpoints & Workflow

1. **`/ingest`**: Upload a PDF. Text is extracted and saved into the `chunks` table.
    
2. **`/generate-quiz`**: Select a topic and grade. The system calls Gemini AI to create questions and stores them in the `questions` table.
    
3. **`/quiz`**: Access and attempt the generated quiz.
    
4. **`/submit-quiz`**: Submit answers to receive a score. Users can then choose to generate **More Questions** or start a **New Quiz**.
