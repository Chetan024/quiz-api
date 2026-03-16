from fastapi import FastAPI, Request, UploadFile, Depends, Form
from typing import Optional
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.orm import sessionmaker, Session
from database import engine, Base
import database
import models
from contextlib import asynccontextmanager
from pypdf import PdfReader
from google import genai

def init_db():
    Base.metadata.create_all(bind=engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def current_user(db: Session = Depends(get_db)):
    id = 1
    user = db.query(database.User).filter(database.User.user_id==id).first()
    if not user:
        user = database.User(name = "default", user_id = id)
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def chunk(filepath: str, src_id: str):
    reader = PdfReader(filepath)

    all_text = ""
    for page in reader.pages:
        all_text += page.extract_text() + "\n"
        
    lines = [line.strip() for line in all_text.splitlines() if line.strip()]

        
    first_line = lines[0] 
    parts = first_line.split("Grade ")
    grade_and_subject = parts[1].split(" ")

    grade = grade_and_subject[0]
    subject = " ".join(grade_and_subject[1:])

    second_line = lines[1]

    topic = second_line.partition("Topic:")[2].strip()


    remaining_text = "\n".join(lines[2:])
    return database.Chunks(chunk_id = f"{src_id}_01", src_id = src_id, topic = topic, subject = subject, grade = grade, text = remaining_text)

def extract_questions(text: str):
    # 1. Split the text into individual question blocks using double newlines
    question_blocks = text.strip().split('\n\n')

    extracted_data = []

    for block in question_blocks:
        # 2. Split each block into separate lines
        lines = block.strip().split('\n')
        
        q_type = ""
        question = ""
        options = []
        answer = ""
        difficulty = ""
        
        # 3. Process the first line to get Question Type and Question Text
        # Example format: "1. (MCQ) Choose the correct contraction..."
        first_line = lines[0]
        if "(" in first_line and ")" in first_line:
            start_idx = first_line.find("(")
            end_idx = first_line.find(")")
            
            # Extract type (e.g., MCQ, True/False, Fill)
            q_type = first_line[start_idx + 1 : end_idx]
            
            # Extract question (everything after the type)
            question = first_line[end_idx + 1:].strip()
        
        # 4. Iterate through the rest of the lines for Answer, Difficulty, and Options
        for line in lines[1:]:
            line = line.strip()
            
            if line.startswith("Answer:"):
                answer = line.replace("Answer:", "").strip()
                
            elif line.startswith("Difficulty:"):
                difficulty = line.replace("Difficulty:", "").strip()
                
            elif any(line.startswith(prefix) for prefix in ["A.", "B.", "C.", "D."]):
                options.append(line)
                
        # 5. Store the extracted components into a dictionary
        ques = models.Questions(question=question, 
                                type=q_type, 
                                options=options, 
                                answer=answer,
                                difficulty=difficulty)
        extracted_data.append(ques)
    return extracted_data

async def llm_question_generate(chunk: database.Chunks):
    client = genai.Client()
    prompt = f"""Role: You are an expert educational assessment designer.
    Task: Generate a set of {chunk.topic} questions based on the details below.
    Parameters:
    Topic: {chunk.topic}
    Grade Level: {chunk.grade}
    Format Rules:
    Use labels: (MCQ), (True/False), or (Fill).
    List the question followed by the correct answer on the line below it.
    Include a Difficulty Rating: (Easy, Medium, or Hard) for every question based on the specified grade level on the line below answer.
    Do not include any introductory or concluding conversational text.
    Style Reference Example: 
    {chunk.text}
    Please generate the questions now and seprate each question with two blank lines"""

    response = client.models.generate_content(
    model="gemma-3-27b-it",
    contents=prompt)

    return extract_questions(response.text)


@app.get("/ingest", response_class=HTMLResponse)
def ingest_render(request:Request):
    return templates.TemplateResponse("ingest.html", {"request":request})

@app.post("/ingest")
async def ingest(file: UploadFile, db: Session = Depends(get_db)):
    try:
        upload_dir = Path.home() / "Projects"
        upload_dir.mkdir(parents=True, exist_ok=True)
        file_path = upload_dir / file.filename

        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        existing_doc = db.query(database.Documents).filter(database.Documents.doc_url == str(file_path)).first()
        if existing_doc:
            return {"message": "File already exists in database.", "src_id": existing_doc.src_id}
        
        source_id = database.id_gen("src")
        db_doc = database.Documents(doc_url = str(file_path), src_id = source_id)
        db.add(db_doc)

        db_chunk = chunk(str(file_path), source_id)
        db.add(db_chunk)

        db.commit()
        db.refresh(db_doc)
        db.refresh(db_chunk)

        return {"message": "File saved successfully to database.", "src_id": db_doc.src_id, "chunk_id":db_chunk.chunk_id}

    except Exception as e:
        return {"message": str(e)}

@app.get("/generate-quiz", response_class=HTMLResponse)
def generate_quiz_topic_select(request: Request, db: Session = Depends(get_db)):
    results = (
        db.query(database.Chunks.grade, database.Chunks.topic)
        .group_by(database.Chunks.grade, database.Chunks.topic)
        .order_by(database.Chunks.grade)
        .all()
    )

    grades_and_topics = {}
    for grade, topic in results:
        if grade not in grades_and_topics:
            grades_and_topics[grade] = []
        grades_and_topics[grade].append(topic)
    
    return templates.TemplateResponse("generate_quiz.html", {"request": request, "grades_topics": grades_and_topics})

@app.post("/generate-quiz", response_class=RedirectResponse)
async def generate_quiz(request: Request, 
                  grade: Optional[str]= Form(None), 
                  topic: Optional[str] = Form(None),
                  db: Session = Depends(get_db)):
    try:
        if request.headers.get("content-type", "").startswith("application/json"):
            data = await request.json()
            grade = data.get("grade")
            topic = data.get("topic")
        
        chunks = db.query(database.Chunks).filter(
            database.Chunks.grade == grade,
            database.Chunks.topic == topic
        ).all()
        
        for chunk in chunks:
            ch_q = db.query(database.Questions).filter(database.Questions.src_chunk_id == chunk.chunk_id).first()
            if ch_q:
                continue
            questions = await llm_question_generate(chunk)
            for question in questions:
                db_ques = database.Questions(**question.model_dump(),src_chunk_id=chunk.chunk_id)
                db.add(db_ques)
            db.commit()
        
        return RedirectResponse(url=f"/quiz?topic={topic}&grade={grade}", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        return {"message": str(e)}


global_questions=[]
quiz_questions = []
@app.get("/quiz", response_class=HTMLResponse)
def get_quiz(request: Request, db: Session = Depends(get_db)):
    topic = request.query_params.get("topic")
    grade = request.query_params.get("grade")

    if len(global_questions) >= 2 and (global_questions[0]==topic and global_questions[1]==grade):
        pass
    else:
        questions = []
        results = (db.query(database.Chunks.chunk_id).filter(
            database.Chunks.grade == grade).filter(database.Chunks.topic == topic).distinct().all())
        chunk_ids = [r[0] for r in results]
        for id in chunk_ids:
            temp = db.query(database.Questions).filter(
                    database.Questions.src_chunk_id == id
                ).all()
            questions.extend(temp)
        global_questions.clear()
        global_questions.append(topic)
        global_questions.append(grade)
        global_questions.extend(questions)

    quiz_questions.clear()
    if len(global_questions)<=2:
        return templates.TemplateResponse("no_more_questions.html", {"request":request})
    
    questions = global_questions[2:7]
    quiz_questions.extend(questions)
    if request.query_params.get("score") is not None:
        del global_questions[2:7]
        
    return templates.TemplateResponse("quiz.html", {"request": request,"questions": questions, "grade": grade, "topic": topic})

@app.post("/submit-answers", response_class=HTMLResponse)
async def submit_answers(request: Request):
    form_data = await request.form()
    
    score = 0
    grade = form_data.get("grade")
    topic = form_data.get("topic")
    for question in quiz_questions:
        if question.type == "MCQ":
            selected_option = form_data.get(f"{question.question_id}")
            if selected_option:
                splitted = selected_option.split(" ") 
                user_answer = " ".join(splitted[1:])
            else:
                user_answer = ""
        else:
            user_answer = form_data.get(f"{question.question_id}")
        
        print(user_answer)
        print(question.answer)
        is_correct = (user_answer == question.answer)

        if is_correct:
            score+=1
    
    print(score)
    return templates.TemplateResponse("submit_answers.html",{"request": request, "score": score, "grade":grade, "topic": topic})
