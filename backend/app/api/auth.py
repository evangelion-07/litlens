from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.services import accounts
from app.services.user_context import profile_user

router = APIRouter(prefix="/auth", tags=["Local accounts"])


class Credentials(BaseModel):
    username: str = Field(min_length=3, max_length=40, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=10, max_length=128)


class Registration(Credentials):
    display_name: str = Field(min_length=1, max_length=80, pattern=r".*\S.*")


@router.post("/register", status_code=201)
def register(body: Registration):
    return accounts.register(body.username, body.display_name, body.password)


@router.post("/login")
def login(body: Credentials):
    return accounts.login(body.username, body.password)


@router.get("/me")
def me():
    return profile_user.get()


@router.post("/logout")
def logout(request: Request):
    accounts.logout(request.headers.get("authorization", "").removeprefix("Bearer "))
    return {"signed_out": True}
