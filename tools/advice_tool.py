# FINAL_PROJECT/tools/advice_tool.py

#  특정 종목에 대해 구조화된 형식의 투자 조언을 생성

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
import os
from typing import Tuple, Any

from tools.symbol_resolver import resolve_symbol
from tools.stock_price_tool import get_stock_price

from langchain_core.tools import tool 

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    openai_api_key=api_key
)

# advice_tool.py 파일에서 advice_prompt 부분을 이 내용으로 교체해주세요.

# advice_tool.py 파일에서 advice_prompt 부분을 이 내용으로 교체해주세요.

# advice_tool.py 파일에서 advice_prompt 부분을 이 내용으로 교체해주세요.

advice_prompt = PromptTemplate.from_template("""
You are a helpful assistant that provides stock analysis in a structured format in KOREAN.
You MUST follow the user's requested format EXACTLY.

The user wants the output in the following format. Do not add any text before or after this structure.
[요약]
(2-3 sentences summary)

[장점]
- (Pro 1)
- (Pro 2)

[리스크]
- (Risk 1)
- (Risk 2)

[결론(한 줄)]
(A single, neutral summary sentence)

---
Now, provide the analysis for the following stock based on the provided context. Remember to use the EXACT format above.

Stock: {symbol}
Context: {context}

Structured Analysis:
""")

chain = advice_prompt | llm | StrOutputParser()

@tool
def get_stock_advice(name_or_symbol: str) -> str:
    """
    한국어 종목명 또는 티커를 받아서
    1) 티커로 해석(resolve)
    2) (선택) 현재가 한 줄을 컨텍스트로 주입
    3) 프롬프트 체인 실행
    """
    sym = resolve_symbol(name_or_symbol)
    if not sym:
        return f"❌ 종목을 찾지 못했습니다: '{name_or_symbol}'"

    # get_stock_price 함수의 반환값을 받아 성공 여부로 판단하도록 수정
    is_success, price_line = get_stock_price(sym)
    
    # 성공했을 경우에만 컨텍스트로 주입
    ctx = price_line if is_success else ""

    try:
        return chain.invoke({"symbol": sym, "context": ctx})
    except Exception as e:
        return f"❌ 조언 생성 실패({sym}): {e}"