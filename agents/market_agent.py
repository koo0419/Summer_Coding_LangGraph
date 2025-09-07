# FINAL_PROJECT/agents/market_agent.py

# 외부 API(Marketaux) → LLM(GPT-4) → 알림(Gmail) 으로 이어지는 자동화 파이프라인
import os
import requests
import datetime
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from tools.gmail_tool import gmail_authenticate, send_email

from langchain_core.tools import tool 

# ==============================================================================
# 1. 환경변수 로딩
# ==============================================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MARKETAUX_API_KEY = os.getenv("MARKETAUX_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("❌ OPENAI_API_KEY가 .env 파일에 설정되어 있지 않습니다.")
if not MARKETAUX_API_KEY:
    raise ValueError("❌ MARKETAUX_API_KEY가 .env 파일에 설정되어 있지 않습니다.")

# ==============================================================================
# 2. Marketaux API를 호출하여 최신 미국 경제 뉴스 기사 5개를 가져온다.
# ==============================================================================
def get_marketaux_news(api_key: str) -> str:
    """Marketaux API를 호출하여 최신 미국 경제 뉴스를 가져옵니다."""
    url = "https://api.marketaux.com/v1/news/all"
    params = {
        "api_token": api_key,
        "language": "en",
        "countries": "us", # 미국 전체 시장 뉴스를 가져오도록 수정
        "filter_entities": True
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        news_data = response.json().get("data", [])

        # 뉴스 기사 5개만 선택하여 제목과 요약을 하나의 문자열로 결합
        news_texts = [
            f"Title: {article.get('title', '')}\nSummary: {article.get('description', '')}"
            for article in news_data[:5]
        ]
        return "\n\n".join(news_texts)
    except Exception as e:
        print(f"Marketaux API 호출 오류: {e}")
        return ""

# ==============================================================================
# 3. LangChain LLM & 체인 설정
# ==============================================================================
llm = ChatOpenAI(
    model="gpt-4",
    temperature=0.3,
    openai_api_key=OPENAI_API_KEY
)

briefing_prompt = PromptTemplate.from_template("""
너는 경제 전문가로서 아래 제공된 뉴스 기사들을 바탕으로 오늘의 미국 경제 흐름을 요약해야 해.
- 뉴스 기사들의 핵심 내용을 조합하여 요약할 것
- 할루시네이션은 절대 금지
- 핵심 내용만 간결하게 3줄 요약
- 일반인도 쉽게 이해할 수 있는 표현 사용
- 무조건 한국어로 정리해서 메일 전송할 것

제공된 뉴스 기사:
{news_data}
""")

parser = StrOutputParser()

market_briefing_chain = briefing_prompt | llm | parser

# ==============================================================================
#  4. LangChain과 GPT-4 모델을 이용해 수집한 뉴스들을 3줄의 간결한 요약문으로 생성
# ==============================================================================

@tool
def generate_market_briefing() -> str:
    """Marketaux 뉴스를 가져와 LLM이 요약하도록 합니다."""
    news_data = get_marketaux_news(MARKETAUX_API_KEY)
    if not news_data:
        return "뉴스 데이터를 가져오는 데 실패했습니다. 시장 요약을 생성할 수 없습니다."
        
    return market_briefing_chain.invoke({"news_data": news_data})

# ==============================================================================
# 5. gmail_tool을 활용하여 생성된 요약문을 지정된 이메일 주소로 발송
# ==============================================================================
def send_market_briefing_email(summary: str, to_email: str) -> str:
    """오늘의 경제 요약 이메일을 발송합니다."""
    # 현재 날짜를 포함한 동적 제목 생성
    today = datetime.date.today().strftime("%Y-%m-%d")
    email_subject = f"📊 [{today}] 오늘의 미국 경제 요약"
    
    service = gmail_authenticate()
    result = send_email(service, to_email, email_subject, summary)
    return result