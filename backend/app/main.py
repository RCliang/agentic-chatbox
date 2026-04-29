from fastapi import FastAPI

from app.core.config import settings

app = FastAPI(title="Agentic Chatbox", version="0.1.0")


@app.get("/health")
async def health():
    return {"status": "ok"}
