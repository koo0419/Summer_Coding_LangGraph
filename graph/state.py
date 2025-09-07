# FINAL_PROJECT/graph/state.py

from typing import TypedDict, Annotated, List
import operator
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """
    그래프의 각 단계를 거치며 공유될 상태 객체입니다.

    Attributes:
        messages: 사용자와 AI의 대화 기록 전체를 저장합니다.
                  add_messages는 새 메시지가 기존 메시지에 추가되도록 합니다.
    """
    messages: Annotated[List[BaseMessage], add_messages]