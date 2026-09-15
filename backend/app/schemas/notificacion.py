from pydantic import BaseModel


class PushTokenCreate(BaseModel):
    token: str
    plataforma: str = "android"
