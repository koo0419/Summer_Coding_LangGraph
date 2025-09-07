# FINAL_PROJECT/tools/portfolio_tool.py (최종 완성본)

import os
import requests
from dotenv import load_dotenv
from typing import Optional, Dict, Any
import datetime
import pytz

from langchain_core.tools import tool # ⭐️ langchain_core.tools에서 tool을 import 하도록 수정

load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

def _get_existing_stock(symbol: str) -> Optional[dict]:
    url = f"{SUPABASE_URL}/rest/v1/portfolio?symbol=eq.{symbol}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None
    except Exception:
        return None

def _update_portfolio(symbol: str, payload: Dict[str, Any]) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/portfolio?symbol=eq.{symbol}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    try:
        response = requests.patch(url, headers=headers, json=payload)
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"--- Supabase 업데이트 오류 ---")
        print(f"심볼: {symbol}, 페이로드: {payload}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"상세 오류: {e.response.text}")
        else:
            print(f"오류: {e}")
        print(f"--------------------------")
        return False

def _delete_stock(symbol: str) -> bool:
    url = f"{SUPABASE_URL}/rest/v1/portfolio?symbol=eq.{symbol}"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    try:
        response = requests.delete(url, headers=headers)
        response.raise_for_status()
        return True
    except Exception:
        return False

@tool
def buy_stock(action_input: str) -> str:
    """
    사용자의 요청에 따라 주식을 매수하고 Supabase 포트폴리오에 기록합니다. 평단가를 자동으로 계산합니다.
    Args:
        action_input (str): '종목명,수량,가격' 형식의 문자열 (예: "AAPL,10,200.50").
    """
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return "❌ Supabase 환경 변수가 설정되지 않았습니다."
    try:
        symbol, quantity_str, price_str = action_input.split(',')
        symbol = symbol.strip()
        quantity = int(quantity_str.strip())
        price = float(price_str.strip())
    except ValueError:
        return "❌ 입력 형식이 올바르지 않습니다. '종목명,수량,가격' 형식으로 입력해주세요."

    korea_timezone = pytz.timezone('Asia/Seoul')
    now_kst_iso = datetime.datetime.now(korea_timezone).isoformat()

    existing_stock = _get_existing_stock(symbol)

    if existing_stock:
        old_quantity = existing_stock['quantity']
        old_avg_price = existing_stock['purchase_price']
        
        total_cost = (old_avg_price * old_quantity) + (price * quantity)
        total_quantity = old_quantity + quantity
        
        new_avg_price = total_cost / total_quantity
        
        update_payload = {
            "quantity": total_quantity,
            "purchase_price": new_avg_price,
            "created_at": now_kst_iso # 👈 컬럼명 수정
        }
        if _update_portfolio(symbol, update_payload):
            return (f"✅ {symbol} {quantity}주를 추가 매수했습니다. "
                    f"(총 {total_quantity}주, 평단가: {new_avg_price:,.2f})")
        else:
            return f"❌ {symbol} 정보 업데이트에 실패했습니다."
    else:
        url = f"{SUPABASE_URL}/rest/v1/portfolio"
        headers = {
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "symbol": symbol, 
            "quantity": quantity, 
            "purchase_price": price,
            "created_at": now_kst_iso # 👈 컬럼명 수정
        }
        try:
            requests.post(url, headers=headers, json=payload).raise_for_status()
            return f"✅ {symbol} {quantity}주를 신규 매수하여 Supabase에 기록했습니다."
        except requests.exceptions.RequestException as e:
            return f"❌ Supabase에 거래 기록 실패: {e}"

@tool
def sell_stock(action_input: str) -> str:
    """
    사용자의 요청에 따라 주식을 매도합니다. 매도 후 수량이 0이 되면 포트폴리오에서 자동 삭제됩니다.
    Args:
        action_input (str): '종목명,수량' 형식의 문자열 (예: "AAPL,5").
    """
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        return "❌ Supabase 환경 변수가 설정되지 않았습니다."
    
    try:
        parts = action_input.split(',')
        if len(parts) != 2:
            raise ValueError("입력값은 정확히 2개여야 합니다.")
        symbol = parts[0].strip()
        quantity = int(parts[1].strip())
    except ValueError:
        return "❌ 입력 형식이 올바르지 않습니다. '종목명,수량' 형식으로 입력해주세요. (예: 'AAPL,5')"
    
    existing_stock = _get_existing_stock(symbol)
    if not existing_stock:
        return f"❌ {symbol}을(를) 보유하고 있지 않아 매도할 수 없습니다."
    
    current_quantity = existing_stock['quantity']
    if current_quantity < quantity:
        return f"❌ 매도하려는 수량({quantity}주)이 보유 수량({current_quantity}주)보다 많습니다."

    new_quantity = current_quantity - quantity

    if new_quantity > 0:
        korea_timezone = pytz.timezone('Asia/Seoul')
        now_kst_iso = datetime.datetime.now(korea_timezone).isoformat()
        
        update_payload = {
            "quantity": new_quantity,
            "created_at": now_kst_iso # 👈 컬럼명 수정
        }
        if _update_portfolio(symbol, update_payload):
            return f"✅ {symbol} {quantity}주를 매도했습니다. (남은 수량: {new_quantity}주)"
        else:
            return f"❌ {symbol} 정보 업데이트에 실패했습니다."
    else:
        if _delete_stock(symbol):
            return f"✅ {symbol} {quantity}주를 전량 매도하여 포트폴리오에서 삭제했습니다."
        else:
            return f"❌ {symbol} 종목 삭제에 실패했습니다."