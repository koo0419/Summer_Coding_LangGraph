# FINAL_PROJECT/tools/symbol_resolver.py

# "삼성전자", "애플", "테슬라" 등 사용자의 다양한 언어 표현을 "005930.KS", "AAPL", "TSLA" 와 같은 정확한 주식 **티커(Ticker)**로 변환

import os, re, requests
from typing import Optional, List
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
TD_API_KEY = os.getenv("TWELVE_DATA_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
STRICT = os.getenv("SYMBOL_RESOLVE_STRICT", "0") == "1"  # 기본: 빠르게(검증 최소화)

TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9\.\-]{0,9}$", re.IGNORECASE)

def looks_like_ticker(text: str) -> bool:
    return bool(TICKER_RE.fullmatch(text.strip()))

def is_krx_symbol(sym: str) -> bool:
    s = sym.upper()
    return s.endswith(".KS") or s.endswith(".KQ") or re.fullmatch(r"\d{6}", s) is not None

# ---- (선택) 아주 짧은 검증: yfinance만 1회, 1.5초 타임아웃 ----
def _yf_price(symbol: str) -> Optional[float]:
    try:
        import yfinance as yf
        tk = yf.Ticker(symbol)
        info = getattr(tk, "fast_info", {}) or {}
        p = info.get("last_price")
        if p is None:
            # info 호출은 느릴 수 있으니 STRICT 모드에서만 사용
            if not STRICT:
                return None
            info2 = tk.info
            p = info2.get("regularMarketPrice")
        return float(p) if p is not None else None
    except Exception:
        return None

def _validate_symbol(sym: str) -> bool:
    # 엄격 모드에서만 검증; 기본은 False로 두고 빠르게 넘어감
    if not STRICT:
        return True
    return _yf_price(sym) is not None

def _try_korea_suffixes(code6: str) -> Optional[str]:
    for sfx in (".KS", ".KQ"):
        cand = code6 + sfx
        if _validate_symbol(cand):
            return cand
    return None

# ---- Yahoo 검색(키 불필요, 2초 타임아웃) ----

def _yahoo_search(keyword: str) -> Optional[str]:
    try:
        r = requests.get(
            "https://query1.finance.yahoo.com/v1/finance/search",
            params={"q": keyword, "quotesCount": 6, "newsCount": 0, "listsCount": 0},
            timeout=2,
            headers={"User-Agent": "Mozilla/5.0"}
        )
        r.raise_for_status()
        data = r.json() or {}
        quotes = data.get("quotes") or []
        
        # ✅ 주식(EQUITY)을 우선적으로 찾기 위한 로직 추가
        equity_symbol = None
        first_symbol = None
        
        # 한국어 검색 시 KRX 우선 (이전 로직은 유지)
        is_kor = any('\uac00' <= ch <= '\ud7a3' for ch in keyword)
        if is_kor:
            for q in quotes:
                sym = (q.get("symbol") or "").upper()
                if sym.endswith(".KS") or sym.endswith(".KQ"):
                    return sym if not STRICT or _validate_symbol(sym) else None
        
        # 주식(EQUITY) 우선 선택 로직
        for q in quotes:
            sym = (q.get("symbol") or "").upper()
            if not sym: continue
            
            # 첫 번째 결과를 일단 저장 (폴백용)
            if first_symbol is None:
                first_symbol = sym
            
            # 검색 결과가 '주식' 타입이면 equity_symbol에 저장
            if q.get("quoteType") == "EQUITY":
                # 만약 키워드와 티커가 정확히 일치하는 주식을 찾으면 즉시 반환
                if sym == keyword.upper():
                    return sym
                if equity_symbol is None:
                    equity_symbol = sym

        # 주식을 찾았다면 주식 티커를, 못 찾았다면 그냥 첫 번째 결과를 반환
        return equity_symbol or first_symbol

    except Exception:
        pass
    return None

# ---- LLM 후보(백업, 2초 모델 호출 피하려면 OFF 가능) ----
def _llm_candidates(name: str, top_k: int = 3) -> List[str]:
    if not OPENAI_API_KEY:
        return []
    try:
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, openai_api_key=OPENAI_API_KEY, timeout=2.0)
        system = ("Convert company names (Korean/English) into tickers. "
                  "Prefer 6-digit+.KS/.KQ for Korean; AAPL/TSLA for US. "
                  "Return ONLY 1-3 tickers, comma-separated.")
        user = f"Name: {name}\nTickers only."
        resp = llm.invoke([{"role":"system","content":system},{"role":"user","content":user}])
        text = (getattr(resp, "content", "") or "").upper()
        raw  = re.split(r"[,\s]+", text)
        out: List[str] = []
        for t in raw:
            t = t.strip().upper()
            if not t: continue
            if looks_like_ticker(t) or re.fullmatch(r"\d{6}", t):
                out.append(t)
            if len(out) >= top_k: break
        return out
    except Exception:
        return []

# ---- 메인 ----
COMMON_FIX = {"APPL": "AAPL"}  # 흔한 오타 교정(즉시)

def resolve_symbol(name_or_ticker: str) -> Optional[str]:
    if not name_or_ticker:
        return None
    raw = name_or_ticker.strip()

    # 흔한 오타 즉시 교정
    up = raw.upper()
    if up in COMMON_FIX:
        up = COMMON_FIX[up]

    # 이미 티커면(또는 6자리 숫자) 바로 처리
    if looks_like_ticker(up):
        if re.fullmatch(r"\d{6}", up):
            res = _try_korea_suffixes(up) or (up + ".KS" if not STRICT else None)
            return res
        return up if _validate_symbol(up) else None

    # 1) Yahoo 검색(빠름)
    sym = _yahoo_search(raw)
    if sym:
        return sym

    # 2) LLM 후보 → (선택) 간단 검증
    for cand in _llm_candidates(raw):
        if re.fullmatch(r"\d{6}", cand):
            res = _try_korea_suffixes(cand) or (cand + ".KS" if not STRICT else None)
            if res: return res
        else:
            if not STRICT or _validate_symbol(cand):
                return cand

    return None