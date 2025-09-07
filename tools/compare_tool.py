# FINAL_PROJECT/tools/compare_tool.py

# 두 개의 주식 종목 정보를 비교하여, 상세한 분석 리포트를 생성

import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

from tools.stock_price_tool import get_stock_price
from tools.advice_tool import get_stock_advice

from langchain_core.tools import tool 

# LLM 체인 설정
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)
comparison_prompt = PromptTemplate.from_template(
    """너는 두 주식의 장단점을 비교하여 투자자에게 조언하는 금융 분석가야.
아래에 제공된 두 종목의 정보를 바탕으로, 두 종목의 특징을 중립적인 관점에서 비교하고 종합적인 의견을 1~2문단으로 요약해줘.

[종목 1: {s1_name} 정보]
- 현재가: {s1_price}
- 장점: {s1_pros}
- 리스크: {s1_risks}

[종목 2: {s2_name} 정보]
- 현재가: {s2_price}
- 장점: {s2_pros}
- 리스크: {s2_risks}

[비교 분석]
"""
)
comparison_chain = comparison_prompt | llm | StrOutputParser()

@tool
def compare_two_stocks(symbols: List[str]) -> str:
    """
    두 종목의 주가와 조언을 병렬로 가져와 비교 브리핑을 생성합니다.
    """
    cleaned_symbols = [s.strip() for s in symbols]

    if len(cleaned_symbols) < 2:
        return "비교할 종목을 2개 이상 입력해 주세요. 예: 'TSLA와 AAPL 비교해줘'"

    s1, s2 = cleaned_symbols[0], cleaned_symbols[1]
    results: Dict[str, Dict[str, Any]] = {s1: {}, s2: {}}

    with ThreadPoolExecutor(max_workers=4) as ex:
        futures = {
            ex.submit(get_stock_price, s1): (s1, "price"),
            ex.submit(get_stock_price, s2): (s2, "price"),
            ex.submit(get_stock_advice, s1): (s1, "advice"),
            ex.submit(get_stock_advice, s2): (s2, "advice"),
        }
        for fut in as_completed(futures):
            symbol, result_type = futures[fut]
            try:
                result = fut.result()
                if result_type == "price":
                    is_success, content = result
                    results[symbol]["price"] = content if is_success else f"❌ 주가 조회 실패: {content}"
                else:
                    results[symbol]["advice"] = result
            except Exception as e:
                results[symbol][result_type] = f"❌ {result_type} 조회 실패: {e}"

    def format_advice_section(advice_text: str) -> Dict[str, str]:
        if "❌" in advice_text:
            return {"요약": advice_text, "장점": "정보 없음", "리스크": "정보 없음"}
        try:
            summary = (re.search(r"\[요약\]\s*([\s\S]*?)\s*\[장점\]", advice_text, re.DOTALL).group(1) or "").strip()
            pros = (re.search(r"\[장점\]\s*([\s\S]*?)\s*\[리스크\]", advice_text, re.DOTALL).group(1) or "").strip().replace("- ", "")
            risks = (re.search(r"\[리스크\]\s*([\s\S]*?)\s*(\[결론\(한 줄\)\]|\[결론\])", advice_text, re.DOTALL).group(1) or "").strip().replace("- ", "")
            return {"요약": summary, "장점": pros, "리스크": risks}
        except Exception:
            return {"요약": advice_text, "장점": "파싱 실패", "리스크": "파싱 실패"}

    s1_advice_data = format_advice_section(results[s1].get('advice', '정보 없음'))
    s2_advice_data = format_advice_section(results[s2].get('advice', '정보 없음'))

    comparison_summary = comparison_chain.invoke({
        "s1_name": s1,
        "s1_price": results[s1].get('price', '정보 없음'),
        "s1_pros": s1_advice_data.get('장점', '정보 없음'),
        "s1_risks": s1_advice_data.get('리스크', '정보 없음'),
        "s2_name": s2,
        "s2_price": results[s2].get('price', '정보 없음'),
        "s2_pros": s2_advice_data.get('장점', '정보 없음'),
        "s2_risks": s2_advice_data.get('리스크', '정보 없음'),
    })
    
    final_output = f"""
✅ **{s1} vs {s2} 비교 분석**
---
### 📊 **{s1}** 분석 요약
- **현재가**: {results[s1].get('price', '정보 없음')}
- **주요 장점**: {s1_advice_data.get('장점', '정보 없음')}
- **주요 리스크**: {s1_advice_data.get('리스크', '정보 없음')}
### 📊 **{s2}** 분석 요약
- **현재가**: {results[s2].get('price', '정보 없음')}
- **주요 장점**: {s2_advice_data.get('장점', '정보 없음')}
- **주요 리스크**: {s2_advice_data.get('리스크', '정보 없음')}
---
### ⚖️ **AI 종합 비교 분석**
{comparison_summary}
---
※ 투자 판단의 최종 책임은 사용자에게 있으며, 본 내용은 정보 제공 목적입니다.
"""
    return final_output.strip()