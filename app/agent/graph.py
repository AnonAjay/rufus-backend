from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agent.emotion import get_current_emotion
from app.agent.llm_router import get_completion
from app.agent.memory import conversation_memory


SYSTEM_PROMPT = (
    "You are Rufus, a companion robot dog assistant. Keep replies voice-friendly: "
    "use 1-3 short spoken sentences unless the user explicitly asks for more detail. "
    "Do not use markdown, bullet points, headers, or numbered lists because replies "
    "will be read aloud through text-to-speech. Ask at most one question per reply. "
    "Do not hedge excessively or repeatedly say you are an AI; respond as a capable, "
    "present assistant. Reminder, WhatsApp, and home-control tool-calling are not "
    "wired up yet, so do not claim you can perform those actions."
)


class AgentState(TypedDict):
    session_id: str
    message: str
    reply: str
    model_used: str


async def chat_node(state: AgentState) -> AgentState:
    session_id = state["session_id"]
    user_message = state["message"]
    emotion = get_current_emotion(session_id)
    history = conversation_memory.get_history(session_id)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current observed user emotion: {emotion}."},
        *history,
        {"role": "user", "content": user_message},
    ]

    completion = await get_completion(messages)
    reply = str(completion)
    conversation_memory.add_message(session_id, "user", user_message)
    conversation_memory.add_message(session_id, "assistant", reply)

    return {
        **state,
        "reply": reply,
        "model_used": getattr(completion, "model_used", "ollama"),
    }


def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("chat", chat_node)
    graph.set_entry_point("chat")
    graph.add_edge("chat", END)
    return graph.compile()


agent_graph = _build_graph()


async def run_agent(session_id: str, message: str) -> AgentState:
    return await agent_graph.ainvoke(
        {
            "session_id": session_id,
            "message": message,
            "reply": "",
            "model_used": "",
        }
    )
