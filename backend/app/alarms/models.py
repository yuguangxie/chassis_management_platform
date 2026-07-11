from pydantic import BaseModel

class Alarm(BaseModel):
    id: str
    level: int
    label: str
    description: str
    status: str = "active"
