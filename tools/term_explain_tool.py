# FINAL_PROJECT/tools/term_explain_tool.py

# finance_terms.pdf 파일의 내용을 기반으로, 사용자가 모를 수 있는 전문 금융 용어를 정확하게 설명하는 RAG 파이프라인
import os
from typing import List, Tuple

from dotenv import load_dotenv
from langchain_community.document_loaders import PyMuPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever
from langchain_openai import OpenAIEmbeddings, ChatOpenAI

# ===== 기본 설정 =====
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PDF_PATH = os.path.join("data", "finance_terms.pdf")
PERSIST_DIR = os.path.join("data", "chroma_terms")

# 한글 잘 되는 최신 임베딩 지정 (하나만 만들어 재사용)
EMB = OpenAIEmbeddings(model="text-embedding-3-small", api_key=OPENAI_API_KEY)

# 캐시(최초 1회 로드)
_DOC_CHUNKS = None
_BM25 = None


# PDF 문서를 잘게 쪼개(Chunking) 벡터로 변환하고, ChromaDB라는 벡터 데이터베이스에 저장
def build_vectorstore():
    """PDF → 청크 → 임베딩(소배치) → Chroma (자동 저장)"""
    print("📄 PDF 로딩 중...")
    loader = PyMuPDFLoader(PDF_PATH)
    docs = loader.load()
    print(f"✅ {len(docs)}개 문서 로드")

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_documents(docs)
    print(f"✂️ {len(chunks)}개 청크 생성")

    # persist_directory 지정만 하면 자동 저장됨 (persist() 호출 X)
    vs = Chroma(embedding_function=EMB, persist_directory=PERSIST_DIR)

    BATCH = 64
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        print(f"➡️ 인덱싱 중... {i+1} ~ {i+len(batch)}")
        vs.add_documents(batch)

    print("✅ 인덱싱 완료 (자동 저장됨):", PERSIST_DIR)

def _load_vectorstore() -> Chroma:
    """persist된 Chroma 불러오기"""
    return Chroma(embedding_function=EMB, persist_directory=PERSIST_DIR)


def _load_chunks_for_bm25() -> Tuple[List, BM25Retriever]:
    """BM25용 청크/리트리버 메모리 로드(최초 1회)"""
    global _DOC_CHUNKS, _BM25
    if _DOC_CHUNKS is None:
        loader = PyMuPDFLoader(PDF_PATH)
        docs = loader.load()
        splitter = RecursiveCharacterTextSplitter(chunk_size=700, chunk_overlap=120)
        _DOC_CHUNKS = splitter.split_documents(docs)
        _BM25 = BM25Retriever.from_documents(_DOC_CHUNKS)
        _BM25.k = 6
    return _DOC_CHUNKS, _BM25


def _format_sources(docs: List) -> str:
    """출처 페이지 표시 (1-base)"""
    pages = sorted({(d.metadata.get("page", 0) + 1) for d in docs})
    if not pages:
        return ""
    page_str = ", ".join(map(str, pages[:8])) + ("…" if len(pages) > 8 else "")
    return f"\n\n출처: 한국은행 『경제금융용어 700선』 (p. {page_str})"


# ===== RAG 메인 =====
def explain_term(query: str, k: int = 4) -> str:
    """PDF 기반 RAG: 정의 → 핵심 포인트 → 한 줄 예시 (+출처 페이지)"""
    if not os.path.exists(PERSIST_DIR) or not os.listdir(PERSIST_DIR):
        return "아직 용어집 인덱스가 없어요. 먼저 벡터스토어를 생성해주세요."

    vs = _load_vectorstore()

    # 1) 임베딩 유사도 검색 (새 API: invoke)
    retriever = vs.as_retriever(search_kwargs={"k": max(8, k)})
    try:
        contexts = retriever.invoke(query)
    except Exception:
        # 구버전 호환
        contexts = retriever.get_relevant_documents(query)

    # 2) 빈약하면 BM25 키워드 검색 병합
    if len(contexts) < 2:
        _, bm25 = _load_chunks_for_bm25()
        bm_hits = bm25.get_relevant_documents(query)
        seen, merged = set(), []
        for d in (contexts + bm_hits):
            key = (d.metadata.get("page"), d.page_content[:60])
            if key not in seen:
                merged.append(d)
                seen.add(key)
        contexts = merged[:max(8, k)]

    if not contexts:
        return f"'{query}' 관련 내용을 PDF에서 찾지 못했어요. 다른 표현으로 물어봐줄래?"

    # 컨텍스트 묶기
    ctx_texts = "\n\n".join([c.page_content.strip() for c in contexts])

    # LLM 호출
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, api_key=OPENAI_API_KEY)
    system_msg = (
        "너는 금융 용어 설명 어시스턴트다. 반드시 제공된 컨텍스트에만 근거해 답해.\n"
        "형식: ① 정의(두세 문장) ② 핵심 포인트(불릿 3~5개) ③ 한 줄 예시\n"
        "출처에 없는 내용은 추측하지 말고, 모르면 모른다고 말해."
    )
    user_msg = (
        f"[질문]\n{query}\n\n"
        f"[컨텍스트]\n{ctx_texts}\n\n"
        "위 컨텍스트만 활용해 한국어로 설명해줘."
    )
    resp = llm.invoke([
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ])
    answer = resp.content.strip()
    return answer + _format_sources(contexts)


# === LangChain Tool 래퍼 ===
from langchain.tools import Tool

def get_term_explain_tool() -> Tool:
    """
    LangChain Tool로 감싸서 ZeroShotAgent/Router에서 호출 가능하게 함.
    """
    return Tool(
        name="TermExplain",
        description=(
            "한국은행 『경제금융용어 700선』 PDF 기반으로 경제/금융 용어를 설명한다. "
            "사용자는 용어(예: 디플레이션, 듀레이션, 테이퍼링 등)를 한국어로 물어본다."
        ),
        func=lambda q: explain_term(q),
    )