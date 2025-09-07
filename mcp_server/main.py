# FINAL_PROJECT/mcp_server/main.py

import os
import datetime
import pytz # pytz 라이브러리 import
from fastapi import FastAPI, HTTPException
from notion_client import Client
from dotenv import load_dotenv

from models import ChatRecord

# .env 파일 로드
load_dotenv()

# 환경 변수에서 Notion API Key와 DB ID 가져오기
NOTION_API_KEY = os.getenv("NOTION_API_KEY")
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID")

# Notion 클라이언트 초기화
notion_client = Client(auth=NOTION_API_KEY)

app = FastAPI()

@app.post("/record_chat")
async def record_chat(record: ChatRecord):
    """
    사용자와 AI의 대화 내용을 Notion 데이터베이스에 기록합니다.
    """
    if not NOTION_DATABASE_ID:
        raise HTTPException(status_code=500, detail="Notion database ID is not set.")

    try:
        # 현재 시간을 한국 시간대(KST)로 설정
        korea_timezone = pytz.timezone('Asia/Seoul')
        now_kst = datetime.datetime.now(korea_timezone)

        notion_client.pages.create(
            parent={"database_id": NOTION_DATABASE_ID},
            properties={
                "사용자 질문": {"title": [{"text": {"content": record.user_question}}]},
                "AI 응답": {"rich_text": [{"text": {"content": record.ai_response}}]},
                "타임스탬프": {"date": {"start": now_kst.isoformat()}} # 수정된 시간 사용
            }
        )
        return {"status": "success", "message": "Chat recorded successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))