from pydantic import BaseModel
from typing import Optional, Literal

class User(BaseModel):
    name : str

class Questions(BaseModel):
    question : str 
    type : Literal["MCQ", "Fill", "True/False"]
    options : Optional[list[str]]= None
    answer : str
    difficulty : Literal["Easy", "Medium", "Hard"]