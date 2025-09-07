# FINAL_PROJECT/app.py (최종 완성본)

# venv/scripts/activate
# cd mcp_server
# uvicorn main:app --reload

import gradio as gr
import uuid
import json
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_openai import ChatOpenAI
import requests
import os
import threading

from graph.builder import graph
from agents.market_agent import generate_market_briefing, send_market_briefing_email

# --- CSS 파일 직접 읽어오기 ---
try:
    with open("style.css", "r", encoding="utf-8") as f:
        custom_css = f.read()
except FileNotFoundError:
    print("경고: style.css 파일을 찾을 수 없습니다. 기본 스타일로 실행됩니다.")
    custom_css = ""

# --- 헬퍼 함수 ---
def parse_tool_call(tool_calls):
    if not tool_calls:
        return ""
    call = tool_calls[0]
    return f"**도구:** `{call['name']}`\n**파라미터:** `{json.dumps(call['args'], ensure_ascii=False)}`"

def synthesize_final_question(original_question: str, modification_request: str) -> str:
    """LLM을 이용해 원래 질문과 수정 요청을 바탕으로 최종 질문을 생성합니다."""
    try:
        llm = ChatOpenAI(model=os.getenv("TOOL_LLM_MODEL", "gpt-4o-mini"), temperature=0)
        prompt = f"""
        기존 질문과 사용자의 수정 요청을 바탕으로, 하나의 완성된 최종 질문을 재구성해줘.
        오직 재구성된 질문 자체만 간결하게 반환해. 다른 부연 설명은 절대 덧붙이지 마.
        # 기존 질문:
        {original_question}
        # 수정 요청:
        {modification_request}
        # 최종 질문:
        """
        response = llm.invoke(prompt.strip())
        return response.content.strip()
    except Exception as e:
        print(f"❌ 질문 재구성 실패: {e}")
        return modification_request

# --- Notion 기록 함수 ---
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000")

def record_chat_to_notion(user_input: str, ai_response: str):
    try:
        url = f"{MCP_SERVER_URL}/record_chat"
        payload = {"user_question": user_input, "ai_response": ai_response}
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()
        print("✅ 대화 내용이 Notion에 성공적으로 기록되었습니다.")
    except requests.exceptions.RequestException as e:
        print(f"❌ Notion 기록 실패: {e}")

# --- 이메일 발송 함수 (백그라운드 실행용) ---
def send_briefing_in_background():
    """뉴스 요약 이메일을 생성하고 발송합니다."""
    print("🚀 앱 시작 시 뉴스 브리핑 이메일을 백그라운드에서 발송합니다...")
    try:
        summary = generate_market_briefing.invoke({})
        result = send_market_briefing_email(summary, "jeasungkoo@gmail.com")
        print("📬 이메일 발송 완료!", result)
    except Exception as e:
        print(f"❌ 이메일 발송 중 오류 발생: {e}")


# --- Gradio 앱 로직 ---
with gr.Blocks(theme=gr.themes.Base(), css=custom_css) as demo:
    thread_id = gr.State(value="")
    tool_call_info = gr.State(value={})
    active_question = gr.State(value="")

    gr.Markdown(
        """
        # 🤖 주식 조언 AI 시스템 (LangGraph ver.)
        궁금한 주식 관련 질문을 해보세요! AI가 외부 도구를 사용해야 할 때, 실행 권한을 물어볼 거예요.
        """
    )

    with gr.Row(equal_height=True, elem_id="two_col"):
        # 왼쪽: 채팅 + 입력창
        with gr.Column(scale=7, min_width=600):
            chatbot = gr.Chatbot(
                [],
                elem_id="chatbot",
                type="messages",
                height=600,
            )

            with gr.Row():
                txt = gr.Textbox(
                    scale=4,
                    show_label=False,
                    placeholder="궁금한 것을 물어보세요.",
                    container=False,
                )

        # 오른쪽: 도구 승인/수정 패널
        with gr.Column(scale=3, min_width=320, elem_id="hil_panel", visible=False) as hil_section:
            gr.Markdown("**AI가 다음 작업을 계획했습니다. 진행할까요?**")
            tool_plan = gr.Markdown()

            with gr.Row():
                with gr.Column(scale=1, min_width=120):
                    approve_btn = gr.Button("✅ 진행", variant="primary")
                with gr.Column(scale=2):
                    modify_input = gr.Textbox(show_label=False, placeholder="수정할 내용 입력...")
                    modify_btn = gr.Button("📝 파라미터 수정")
                with gr.Column(scale=2):
                    reject_input = gr.Textbox(show_label=False, placeholder="새로운 질문 입력...")
                    reject_btn = gr.Button("❌ 새 질문 입력")

    def handle_user_message(user_message, history, tid):
        if not user_message.strip():
            return history, tid, "", {}, gr.update(visible=False), gr.update(value="", interactive=True), user_message
            
        if not tid:
            tid = str(uuid.uuid4())
        config = {"configurable": {"thread_id": tid}}
        
        history.append({"role": "user", "content": user_message})
        
        input_message = HumanMessage(content=user_message)
        
        last_event = None
        for event in graph.stream({"messages": [input_message]}, config=config, stream_mode="values"):
            last_event = event

        messages = last_event.get('messages', [])
        if not messages:
            history.append({"role": "assistant", "content": "오류: AI 응답 처리 불가"})
            return history, tid, "", {}, gr.update(visible=False), gr.update(value="", interactive=True), user_message

        last_ai_message = messages[-1]

        if not hasattr(last_ai_message, 'tool_calls') or not last_ai_message.tool_calls:
            history.append({"role": "assistant", "content": last_ai_message.content})
            record_chat_to_notion(user_message, last_ai_message.content)
            return history, tid, "", {}, gr.update(visible=False), gr.update(value="", interactive=True), user_message

        tool_calls = last_ai_message.tool_calls
        history.append({"role": "assistant", "content": "도구 사용이 필요합니다..."})
        return (
            history, tid, parse_tool_call(tool_calls),
            tool_calls, gr.update(visible=True), gr.update(value="", interactive=False), user_message
        )

    def handle_hil_decision(decision, new_input, history, tid, original_tool_calls, current_question):
        config = {"configurable": {"thread_id": tid}}
        
        question_to_log = current_question
        stream_input = None

        if decision == "modify" or decision == "reject":
            # ⭐️ 핵심 수정 1: 사용자의 새 질문을 채팅 기록에 먼저 추가합니다.
            history.append({"role": "user", "content": new_input})
            
            tool_call_id = original_tool_calls[0]['id']
            feedback_tool_message = ToolMessage(
                content=f"사용자가 이전 계획을 거절하고 새로운 지시를 내렸습니다. 반드시 이전 계획은 무시하고, 이 새로운 지시를 따라주세요: '{new_input}'",
                tool_call_id=tool_call_id
            )
            stream_input = {"messages": [feedback_tool_message, HumanMessage(content=new_input)]}
            question_to_log = synthesize_final_question(current_question, new_input)
        else: # approve
            stream_input = None
        
        # ⭐️ 핵심 수정 2: AI의 답변을 위한 빈 공간(placeholder)을 추가합니다.
        history.append({"role": "assistant", "content": "요청 처리 중..."})
        
        last_event = None
        for event in graph.stream(stream_input, config=config, stream_mode="values"):
            last_event = event

        messages = last_event.get('messages', [])
        if not messages:
            history[-1] = {"role": "assistant", "content": "오류: AI 응답 처리 불가"}
            return history, tid, "", {}, gr.update(visible=False), gr.update(interactive=True), question_to_log

        last_ai_message = messages[-1]
        
        if not hasattr(last_ai_message, 'tool_calls') or not last_ai_message.tool_calls:
            final_answer = last_ai_message.content
            history[-1] = {"role": "assistant", "content": final_answer}
            record_chat_to_notion(question_to_log, final_answer)
            return history, tid, "", {}, gr.update(visible=False), gr.update(interactive=True), question_to_log
        else:
            tool_calls = last_ai_message.tool_calls
            history[-1] = {"role": "assistant", "content": "계획을 수정하여 다시 제안합니다..."}
            return (
                history, tid, parse_tool_call(tool_calls),
                tool_calls, gr.update(visible=True), gr.update(interactive=False), question_to_log
            )

    # 이벤트 리스너
    txt.submit(
        handle_user_message,
        [txt, chatbot, thread_id],
        [chatbot, thread_id, tool_plan, tool_call_info, hil_section, txt, active_question]
    )
    
    approve_btn.click(
        handle_hil_decision,
        [gr.State("approve"), gr.State(None), chatbot, thread_id, tool_call_info, active_question],
        [chatbot, thread_id, tool_plan, tool_call_info, hil_section, txt, active_question]
    )
    modify_btn.click(
        handle_hil_decision,
        [gr.State("modify"), modify_input, chatbot, thread_id, tool_call_info, active_question],
        [chatbot, thread_id, tool_plan, tool_call_info, hil_section, txt, active_question]
    )
    reject_btn.click(
        handle_hil_decision,
        [gr.State("reject"), reject_input, chatbot, thread_id, tool_call_info, active_question],
        [chatbot, thread_id, tool_plan, tool_call_info, hil_section, txt, active_question]
    )

if __name__ == "__main__":
    email_thread = threading.Thread(target=send_briefing_in_background)
    email_thread.daemon = True
    email_thread.start()

    demo.launch()