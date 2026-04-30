from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.database import engine
from app.models.base import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import all models so Base.metadata knows about them
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        # Drop and recreate skills table to pick up schema changes
        # (safe because skills are re-seeded from BUILTIN_SKILLS on demand)
        from sqlalchemy import text
        # Clear FK references first
        await conn.execute(text(
            "UPDATE conversations SET skill_id = NULL WHERE skill_id IS NOT NULL"
        ))
        from app.models.skill import Skill as SkillModel
        await conn.execute(text("DROP TABLE IF EXISTS skills CASCADE"))
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(title="Agentic Chatbox", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
