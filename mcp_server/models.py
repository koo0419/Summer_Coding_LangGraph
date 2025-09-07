# FINAL_PROJECT/mcp_server/models.py

# mcp_server/main.py의 FastAPI 서버가 받을 데이터의 형식(Schema)을 정의

from pydantic import BaseModel

class ChatRecord(BaseModel):
    user_question: str
    ai_response: str