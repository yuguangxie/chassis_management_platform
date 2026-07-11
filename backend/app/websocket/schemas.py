from pydantic import BaseModel

class WsCommand(BaseModel):
    action: str
    topics: list[str] = []
