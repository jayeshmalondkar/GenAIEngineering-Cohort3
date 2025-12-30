from pydantic import BaseModel
from typing import List, Optional

class Task(BaseModel):
    # Task model attributes here

class UpdateTask(BaseModel):
    # Update task model attributes here

class NewTask(BaseModel):
    # New task model attributes here

class Dashboard(BaseModel):
    # Dashboard model attributes here

class Notification(BaseModel):
    # Notification model attributes here

class Error(BaseModel):
    code: int
    message: str