# FINAL_PROJECT/main.py

import os
import requests
from dotenv import load_dotenv

from agents.market_agent import generate_market_briefing, send_market_briefing_email
from agents.zero_shot_agent import run_agent

load_dotenv()
# MCP 서버 주소를 환경 변수에서 가져옴
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000")

def send_briefing_on_start():
    summary = generate_market_briefing()
    result = send_market_briefing_email(summary, "jeasungkoo@gmail.com")

def record_chat_to_notion(user_input: str, ai_response: str):
    """
    사용자와 AI의 대화 내용을 Notion MCP 서버로 전송합니다.
    """
    try:
        url = f"{MCP_SERVER_URL}/record_chat"
        payload = {
            "user_question": user_input,
            "ai_response": ai_response
        }
        # MCP 서버에 POST 요청을 보냄
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()  # HTTP 오류 발생 시 예외 발생
        print("✅ 대화 내용이 Notion에 성공적으로 기록되었습니다.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Notion 기록 실패: {e}")

def start_user_prompt_loop():
    while True:
        user_input = input("\n❓ 질문을 입력하세요 (또는 'exit' 입력 시 종료): ")
        if user_input.strip().lower() == "exit":
            print("👋 종료합니다.")
            break

        try:
            response = run_agent(user_input)
        except Exception as e:
            response = f"⚠️ 에이전트 실행 오류: {e}"

        print("\n🤖 AI 응답:")
        print(response)

        # Notion에 대화 내용을 기록하는 함수 호출
        record_chat_to_notion(user_input, response)

if __name__ == "__main__":
    start_user_prompt_loop()
