from fastapi import FastAPI

from app.api.router import api_router
from app.core.config import settings

app = FastAPI(title="Agentic Chatbox", version="0.1.0")

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
