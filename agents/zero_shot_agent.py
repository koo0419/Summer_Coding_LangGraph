# FINAL_PROJECT/agents/zero_shot_agent.py

# LLM이 질문을 읽고 어떤 Tool을 쓸지 판단하는 중앙 판단 Agent

# 사용자의 모든 질문을 가장 먼저 받아서, 그 의도를 파악하고 어떤 도구(Tool)를 사용해야 할지 결정하고 지시하는 역할(중앙 라우터)

from langchain.agents import Tool, initialize_agent
from langchain.agents.agent_types import AgentType
from langchain_openai import ChatOpenAI

from typing import List

from agents.market_agent import generate_market_briefing

from tools.stock_price_tool import get_stock_price
from tools.advice_tool import get_stock_advice
from tools.compare_tool import compare_two_stocks
from tools.term_explain_tool import get_term_explain_tool
from tools.portfolio_tool import buy_stock, sell_stock
from tools.asset_summary_tool import get_portfolio_summary
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

llm = ChatOpenAI(
    model="gpt-4",
    temperature=0,
    openai_api_key=api_key
)

tools = [
    Tool(
        name="GetStockPrice",
        func=get_stock_price,
        description="특정 종목(symbol)의 현재 주가를 조회합니다. 'TSLA 주가 알려줘', 'AAPL 가격은 얼마야?'와 같은 질문에 사용하세요."
    ),
    Tool(
        name="MarketBriefing",
        func=lambda _: generate_market_briefing(),
        description="오늘의 시장 요약을 제공합니다. '오늘 시장 어때?', '경제 요약해줘'와 같은 질문에 사용하세요."
    ),
    Tool(
        name="StockAdvice",
        func=get_stock_advice,
        description="특정 종목(symbol)에 대한 투자 조언을 제공합니다. 'TSLA 전망 어때?', 'AAPL 투자해도 괜찮아?'와 같은 질문에 사용하세요."
    ),
    Tool(
        name="CompareStock",
        func=lambda symbols: compare_two_stocks(symbols.split(", ")),
        description="두 종목을 비교합니다. 사용자의 질문에서 2개의 종목 티커 또는 종목명을 추출하여 쉼표로 구분된 문자열(예: 'TSLA, AAPL')로 전달하세요. 'TSLA와 AAPL 비교해줘'와 같은 질문에 사용하세요.",
        return_direct=True,
    ),
    get_term_explain_tool(),
    Tool(
        name="buy_stock",
        func=buy_stock,
        description="주식을 매수할 때 사용합니다. '매수' 질문에서 종목명, 수량, 가격을 추출하여 '종목명,수량,가격' 형식의 문자열로 전달하세요."
    ),
    Tool(
        name="sell_stock",
        func=sell_stock,
        description="주식을 매도할 때 사용합니다. '매도' 질문에서 종목명, 수량, 가격을 추출하여 '종목명,수량,가격' 형식의 문자열로 전달하세요."
    ),
    Tool(
        name="AssetSummary",
        func=lambda _: get_portfolio_summary(),
        description="현재 보유 중인 모든 주식의 목록, 수량, 평단가 등 전체 포트폴리오 현황을 요약해서 보여줍니다. '내 주식 현황', '포트폴리오 알려줘', '내 자산 보여줘'와 같은 질문에 사용됩니다."
    ),
]


agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
    handle_parsing_errors=True,
)

def run_agent(user_input: str) -> str:
    try:
        result = agent.invoke({"input": user_input})
        return result.get("output", str(result)) if isinstance(result, dict) else str(result)
    except Exception as e:
        return f"⚠️ 에이전트 실행 오류: {e}"