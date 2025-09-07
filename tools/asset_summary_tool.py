# FINAL_PROJECT/tools/asset_summary_tool.py

import os
import re
import requests
from dotenv import load_dotenv
from typing import List, Dict, Any

from tools.stock_price_tool import get_stock_price

from langchain_core.tools import tool 

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

@tool
def get_portfolio_summary() -> str:
    """
    Supabase DB에서 전체 포트폴리오를 조회하고, 현재가와 평가 손익을 통화별로 요약하여 반환합니다.
    """
    url = f"{SUPABASE_URL}/rest/v1/portfolio?select=*"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        portfolio_data = response.json()
    except requests.exceptions.RequestException as e:
        return f"❌ 포트폴리 데이터를 가져오는 중 오류가 발생했습니다: {e}"

    if not portfolio_data:
        return "현재 보유 주식이 없습니다."

    summary_lines = [
        "| 종목 | 보유 수량 | 평단가 | 현재가 | 평가 금액 | 평가 손익 |",
        "|:---:|:---:|:---:|:---:|:---:|:---:|"
    ]
    
    # ✅ [수정] 통화별 총계를 위한 변수 초기화
    total_valuation_krw, total_profit_loss_krw = 0.0, 0.0
    total_valuation_usd, total_profit_loss_usd = 0.0, 0.0

    for stock in portfolio_data:
        symbol = stock.get('symbol')
        quantity = stock.get('quantity', 0)
        purchase_price = stock.get('purchase_price', 0)
        
        is_success, price_info = get_stock_price(symbol)
        
        current_price_str = "조회실패"
        current_price = 0.0
        currency_symbol = '' # 통화 기호 저장용

        if is_success:
            # ✅ [수정] 통화 기호(₩ 또는 $) 뒤의 숫자만 찾는 정규식으로 변경
            match = re.search(r'([₩\$])\s*([\d,.]+)', price_info)
            if match:
                currency_symbol = match.group(1)
                price_value = match.group(2)
                current_price = float(price_value.replace(',', ''))
                current_price_str = f"{currency_symbol}{current_price:,.2f}"
            else: # 만약 통화 기호를 못찾으면 예전 방식으로 한번 더 시도
                fallback_match = re.search(r'[\d,.]+', price_info)
                if fallback_match:
                    current_price = float(fallback_match.group().replace(',', ''))
                    current_price_str = f"{current_price:,.2f}"

        valuation = current_price * quantity
        profit_loss = (current_price - purchase_price) * quantity
        
        # ✅ [수정] 통화에 따라 각기 다른 총계 변수에 더하기
        if '₩' in price_info or (currency_symbol == '₩'):
            total_valuation_krw += valuation
            total_profit_loss_krw += profit_loss
            # 평단가와 평가금액/손익에 원화 표시 추가
            purchase_price_str = f"₩{purchase_price:,.0f}"
            valuation_str = f"₩{valuation:,.0f}"
            profit_loss_str = f"₩{profit_loss:,.0f}"
        else: # 기본값은 달러로 처리
            total_valuation_usd += valuation
            total_profit_loss_usd += profit_loss
            purchase_price_str = f"${purchase_price:,.2f}"
            valuation_str = f"${valuation:,.2f}"
            profit_loss_str = f"${profit_loss:,.2f}"
        
        summary_lines.append(
            f"| {symbol} | {quantity:,} | {purchase_price_str} | {current_price_str} | {valuation_str} | {profit_loss_str} |"
        )
    
    # ✅ [수정] 통화별로 분리된 최종 결과 문자열 생성
    summary_lines.append("\n---")
    summary_lines.append(f"**💰 원화(KRW) 총계**")
    summary_lines.append(f"- 총 평가 금액: ₩{total_valuation_krw:,.0f}")
    summary_lines.append(f"- 총 평가 손익: ₩{total_profit_loss_krw:,.0f}")
    summary_lines.append(f"\n**💰 달러(USD) 총계**")
    summary_lines.append(f"- 총 평가 금액: ${total_valuation_usd:,.2f}")
    summary_lines.append(f"- 총 평가 손익: ${total_profit_loss_usd:,.2f}")
    
    return "\n".join(summary_lines)