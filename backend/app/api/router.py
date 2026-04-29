"""Aggregate all API sub-routers into a single top-level router."""

from fastapi import APIRouter

from app.api.auth import router as auth_router

api_router = APIRouter()
api_router.include_router(auth_router)
