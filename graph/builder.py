# FINAL_PROJECT/graph/builder.py (최종 완성본)

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langchain_core.messages import AIMessage, ToolMessage

from graph.state import AgentState
from config import OPENAI_API_KEY, MAIN_LLM_MODEL

# Tool들을 모두 import 합니다.
from tools.asset_summary_tool import get_portfolio_summary
from tools.compare_tool import compare_two_stocks
from tools.stock_price_tool import get_stock_price
from tools.advice_tool import get_stock_advice
from tools.portfolio_tool import buy_stock, sell_stock
from tools.term_explain_tool import get_term_explain_tool
from agents.market_agent import generate_market_briefing


# 1. 사용할 Tool들을 리스트로 묶습니다.
tools = [
    get_portfolio_summary,
    compare_two_stocks,
    get_stock_price,
    get_stock_advice,
    buy_stock,
    sell_stock,
    get_term_explain_tool(),
    generate_market_briefing,
]


# 2. LLM (Agent의 '뇌')을 설정하고 Tool을 연결합니다.
llm = ChatOpenAI(model=MAIN_LLM_MODEL, temperature=0, api_key=OPENAI_API_KEY)
llm_with_tools = llm.bind_tools(tools)


# 3. 그래프의 노드(Node)와 엣지(Edge) 함수를 정의합니다.
def agent_node(state: AgentState):
    # 1. AI가 답변을 생성합니다.
    response = llm_with_tools.invoke(state["messages"])

    # 2. AI가 Tool을 사용하지 않고 직접 답변했는지 확인합니다.
    if not hasattr(response, 'tool_calls') or not response.tool_calls:
        
        # 3. ⭐️ 추가된 로직: 바로 직전의 메시지가 Tool의 결과물인지 확인합니다.
        #    대화 기록이 1개 이상 있고, 마지막 메시지가 ToolMessage가 아닌 경우에만 고정 문구를 붙입니다.
        if len(state["messages"]) > 0 and not isinstance(state["messages"][-1], ToolMessage):
            disclaimer = "저는 주식 조언 AI입니다. 요청하신 질문은 제 전문 분야가 아니므로, 답변의 정확성이 떨어질 수 있다는 점 참고해주세요.\n\n"
            response.content = disclaimer + response.content

    return {"messages": [response]}

# 4. '경로 안내원' 함수 로직을 명확하고 올바르게 수정합니다.
def should_continue(state: AgentState):
    """마지막 메시지를 보고 다음 경로를 결정합니다."""
    last_message = state["messages"][-1]

    # Case 1: 마지막 메시지가 AI의 메시지이고 Tool Call이 있으면 'tools' 노드로 갑니다.
    if isinstance(last_message, AIMessage) and last_message.tool_calls:
        return "tools"
    
    # Case 2: 그 외의 모든 경우 (AI의 최종 답변 등)에는 그래프를 정상적으로 종료합니다.
    return END


# 5. 그래프를 조립하고 컴파일합니다.
graph_builder = StateGraph(AgentState)

graph_builder.add_node("agent", agent_node)
graph_builder.add_node("tools", ToolNode(tools))

graph_builder.set_entry_point("agent")

# 조건부 엣지가 'tools' 또는 'END'로만 가도록 수정합니다.
graph_builder.add_conditional_edges(
    "agent",
    should_continue,
    {
        "tools": "tools",
        END: END,
    },
)
graph_builder.add_edge("tools", "agent")

memory = MemorySaver()

graph = graph_builder.compile(
    checkpointer=memory,
    interrupt_before=["tools"]
)