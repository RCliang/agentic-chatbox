"""Pydantic schemas for authentication endpoints."""

import uuid

from pydantic import BaseModel, ConfigDict


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    avatar_url: str | None
    department_id: uuid.UUID | None
    position: str | None
    is_dept_admin: bool

    model_config = ConfigDict(from_attributes=True)
