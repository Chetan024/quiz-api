from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Text, JSON, Enum
import sqlalchemy
import uuid

DATABASE_URL = "sqlite:///./app.db"
engine = create_engine(DATABASE_URL)
Base = sqlalchemy.orm.declarative_base()

def id_gen(prefix: str = None):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"

class User(Base):
    __tablename__ = "users"
    name = Column(String, index=True)
    user_id = Column(Integer, primary_key=True, autoincrement=True)

class Documents(Base):
    __tablename__ = "documents"
    src_id = Column(String, primary_key=True)
    doc_url = Column(String, unique=True, index=True)

class Chunks(Base):
    __tablename__ = "chunks"
    chunk_id = Column(String, primary_key=True)
    src_id = Column(String, ForeignKey("documents.src_id"))
    topic = Column(String)
    subject = Column(String)
    grade = Column(Integer)
    text = Column(Text)

class Questions(Base):
    __tablename__ = "questions"
    question_id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, unique=True)
    type = Column(Enum("MCQ","Fill","True/False"))
    options = Column(JSON)
    answer = Column(String)
    difficulty = Column(Enum("Easy", "Medium", "Hard"))
    src_chunk_id = Column(String, ForeignKey("chunks.chunk_id"))