from fastapi import FastAPI, Query, Body
from pydantic import BaseModel
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

# Import the Functions from Assistant
from Assistant import Capture_Knowledge, Ask_Assistant

# Create FastAPI instance
app = FastAPI(title="Knowledge Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------- Request Models -----------

class CaptureRequest(BaseModel):
    url: str
    table_name: str

# ----------- API Endpoints -----------

@app.post("/Capture_Knowledge")
def capture_knowledge(request: CaptureRequest):
    """
    Capture knowledge from the given URL and store in the specified table.
    """
    try:
        result = Capture_Knowledge(request.url, request.table_name)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/Ask_Assistant")
def ask_assistant(
    Chat_Hist = Query(..., description="Chat History"),
    Query: str = Query(..., description="User query string"),
    table_name: str = Query(..., description="Table to search from")
):
    """
    Ask the assistant a question based on captured knowledge.
    """
    try:
        result = Ask_Assistant(Chat_Hist, Query, table_name)
        return result
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------- Main Entrypoint -----------

if __name__ == "__main__":
    # Run locally on localhost:4567
    uvicorn.run("Chat_BackEnd:app", host="0.0.0.0", port=4567, reload=True)
