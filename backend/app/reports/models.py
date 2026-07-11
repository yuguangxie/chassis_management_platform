from pydantic import BaseModel

class ReportSummary(BaseModel):
    id: str
    session_id: str
    result: str
    files: dict
