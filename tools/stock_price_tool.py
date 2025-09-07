# FINAL_PROJECT/tools/stock_price_tool.py

# 주식의 현재 가격을 조회하는 도구

import os
import requests
import time
import math
from typing import Optional, Dict, List, Callable, Any, Tuple
from dotenv import load_dotenv

from tools.symbol_resolver import resolve_symbol, is_krx_symbol
from langchain_core.tools import tool

load_dotenv()
TD_API_KEY = os.getenv("TWELVE_DATA_API_KEY")

# -----------------------------
# TTL 적용 캐시 (프로세스 생존 동안)
# -----------------------------
_price_cache: Dict[str, Dict[str, Any]] = {}

def _cache_get(sym: str, ttl_seconds: int = 60) -> Optional[float]:
    entry = _price_cache.get(sym)
    if entry and (time.time() - entry['timestamp']) < ttl_seconds:
        return entry['price']
    return None

def _cache_set(sym: str, price: float) -> None:
    _price_cache[sym] = {'price': price, 'timestamp': time.time()}

# -----------------------------
# 소스별 헬퍼
# -----------------------------
def _get_price_twelvedata(sym: str) -> Optional[float]:
    if not TD_API_KEY:
        return None
    try:
        r = requests.get(
            "https://api.twelvedata.com/price",
            params={"symbol": sym, "apikey": TD_API_KEY},
            timeout=5,
        )
        r.raise_for_status()
        data = r.json() or {}
        if "price" in data:
            return float(data["price"])
        return None
    except Exception:
        return None

def _get_price_yf(sym: str) -> Optional[float]:
    try:
        import yfinance as yf
        tk = yf.Ticker(sym)
        info = getattr(tk, "fast_info", {}) or {}
        p = info.get("last_price")
        if p is None:
            info2 = tk.info
            p = info2.get("regularMarketPrice")
        return float(p) if p is not None else None
    except Exception:
        return None

def _get_price_yahoo_chart(sym: str) -> Optional[float]:
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
        params = {"range": "1d", "interval": "1m"}
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, params=params, headers=headers, timeout=5)
        r.raise_for_status()
        js = r.json() or {}

        result = (js.get("chart") or {}).get("result") or []
        if not result:
            return None

        meta = result[0].get("meta") or {}
        rmp = meta.get("regularMarketPrice")
        if rmp is not None and not (isinstance(rmp, float) and math.isnan(rmp)):
            return float(rmp)

        def _get_last_valid_close(data_key: str) -> Optional[float]:
            quotes = (result[0].get("indicators") or {}).get(data_key) or []
            if quotes:
                close_list = quotes[0].get("close") or []
                close_vals = [c for c in close_list if c is not None]
                if close_vals:
                    return float(close_vals[-1])
            return None
        
        price = _get_last_valid_close("quote")
        if price is None:
            price = _get_last_valid_close("adjclose")

        return price
    except Exception:
        return None

# -----------------------------
# 보조 함수 (API 호출 로직 간소화)
# -----------------------------
def _try_all(funcs: List[Callable], *args) -> Optional[float]:
    for func in funcs:
        price = func(*args)
        if price is not None:
            return price
    return None

# -----------------------------
# 메인 함수 (반환 타입 변경: Tuple[bool, str])
# -----------------------------

@tool
def get_stock_price(name_or_symbol: str) -> Tuple[bool, str]:
    """
    한국어/티커 입력을 받아 성공 여부와 가격 문자열을 반환합니다.
    """
    symbol = resolve_symbol(name_or_symbol)
    if not symbol:
        return False, f"❌ 종목을 찾지 못했습니다: '{name_or_symbol}'"

    cached = _cache_get(symbol)
    if cached is not None:
        if is_krx_symbol(symbol):
            return True, f"{symbol}의 현재 주가는 ₩{cached:.2f}입니다."
        return True, f"{symbol}의 현재 주가는 ${cached:.4f}입니다."

    if is_krx_symbol(symbol):
        krx_apis = [_get_price_yf, _get_price_yahoo_chart]
        price = _try_all(krx_apis, symbol)
        if price is None:
            return False, f"❌ 국내 종목 가격 조회 실패: {symbol}"
        
        _cache_set(symbol, price)
        return True, f"{symbol}의 현재 주가는 ₩{price:.2f}입니다."

    overseas_apis = [_get_price_twelvedata, _get_price_yf]
    price = _try_all(overseas_apis, symbol)
    if price is None:
        return False, f"❌ 해외 종목 가격 조회 실패: {symbol}"
    
    _cache_set(symbol, price)
    return True, f"{symbol}의 현재 주가는 ${price:.4f}입니다."