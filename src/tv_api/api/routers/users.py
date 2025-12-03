"""Endpoints focused on user interactions."""

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

router = APIRouter(prefix="/user", tags=["user"])


class UserRequest(BaseModel):
    """Payload for creating or validating a user."""

    email: EmailStr


class UserResponse(BaseModel):
    """Echo response for initial integration testing."""

    email: EmailStr
    message: str


@router.post("", summary="Echo user email", response_model=UserResponse)
async def create_user(payload: UserRequest) -> UserResponse:
    """Accept an email address and echo it back."""

    return UserResponse(email=payload.email, message="Email received")
