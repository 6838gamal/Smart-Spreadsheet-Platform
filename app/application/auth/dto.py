"""Data Transfer Objects for authentication."""

from pydantic import BaseModel, EmailStr, field_validator
import re


class RegisterDTO(BaseModel):
    email: EmailStr
    username: str
    password: str
    confirm_password: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be 3–50 characters")
        if not re.match(r"^[a-zA-Z0-9_\u0600-\u06FF]+$", v):
            raise ValueError("Username can only contain letters, numbers, and underscores")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    def check_passwords_match(self) -> None:
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")


class LoginDTO(BaseModel):
    email: str
    password: str


class TokenResponseDTO(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
