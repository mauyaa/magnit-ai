from pydantic import BaseModel


class UserCreateRequest(BaseModel):
    email: str


class UserResponse(BaseModel):
    id: str
    email: str
