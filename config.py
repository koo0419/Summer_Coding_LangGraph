# FINAL_PROJECT/config.py

import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수를 로드합니다.
load_dotenv()

# --- API Keys ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# --- LLM Models ---
# Agent의 판단, 최종 답변 생성 등 핵심 역할을 위한 모델
MAIN_LLM_MODEL = os.getenv("MAIN_LLM_MODEL", "gpt-4o")

# Tool 내부에서 간단한 요약, 변환 등을 위해 사용할 모델 (필요시)
# 현재는 MAIN_LLM_MODEL과 동일하게 설정
TOOL_LLM_MODEL = os.getenv("TOOL_LLM_MODEL", "gpt-4o-mini")


# --- Verification ---
if not OPENAI_API_KEY:
    raise ValueError("환경 변수 'OPENAI_API_KEY'가 설정되지 않았습니다.")