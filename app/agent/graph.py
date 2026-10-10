import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agent.emotion import get_current_emotion
from app.agent.llm_router import get_completion
from app.agent.memory import conversation_memory
from app.agent.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are Rufus, a companion robot dog and desktop assistant. Keep replies voice-friendly: "
    "use 1-3 short spoken sentences unless the user explicitly asks for more detail. "
    "Do not use markdown, bullet points, headers, or numbered lists because replies "
    "will be read aloud through text-to-speech. Ask at most one question per reply. "
    "You have access to tools to open approved apps (WhatsApp, Antigravity, VS Code, Browser, File Explorer), "
    "open websites, search the web / define concepts, and control Spotify. Use these tools when requested. "
    "After an action executes, confirm it warmly in one short sentence."
)


class AgentState(TypedDict):
    session_id: str
    message: str
    reply: str
    model_used: str
    actions: list[str]
    tool_calls: list[dict]
    messages: list[dict]


async def chat_node(state: AgentState) -> AgentState:
    session_id = state["session_id"]
    user_message = state["message"]
    emotion = get_current_emotion(session_id)
    history = conversation_memory.get_history(session_id)

    current_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current observed user emotion: {emotion}."},
        *history,
        {"role": "user", "content": user_message},
    ]

    try:
        completion = await get_completion(current_messages, tools=TOOL_DEFINITIONS)
    except TypeError:
        completion = await get_completion(current_messages)

    reply = str(completion)
    model_used = getattr(completion, "model_used", "ollama")
    tool_calls = getattr(completion, "tool_calls", [])

    current_messages.append({"role": "assistant", "content": reply})

    # If no tools were called, this is the final conversational reply
    if not tool_calls:
        conversation_memory.add_message(session_id, "user", user_message)
        conversation_memory.add_message(session_id, "assistant", reply)

    return {
        **state,
        "reply": reply,
        "model_used": model_used,
        "tool_calls": tool_calls,
        "messages": current_messages,
        "actions": list(state.get("actions", [])),
    }


def should_call_tools(state: AgentState) -> str:
    """Route to tools node only if tool_calls were emitted, otherwise finish immediately."""
    if state.get("tool_calls"):
        return "tools"
    return END


async def tools_node(state: AgentState) -> AgentState:
    """Execute emitted tool calls against strict allowlists."""
    tool_calls = state.get("tool_calls", [])
    actions = list(state.get("actions", []))
    current_messages = list(state.get("messages", []))

    for call in tool_calls:
        tool_name = call.get("name", "")
        tool_args = call.get("arguments", {})
        logger.info("Executing tool: %s with args: %s", tool_name, tool_args)

        tool_result = execute_tool(tool_name, tool_args)

        # Human-readable action badge for UI
        if tool_name == "open_app":
            actions.append(f"Opened {tool_args.get('app_name', 'application').title()}")
        elif tool_name == "open_website":
            actions.append(f"Opened {tool_args.get('url', 'website')}")
        elif tool_name == "web_search":
            actions.append(f"Searched: {tool_args.get('query', '')}")
        elif tool_name == "spotify_control":
            actions.append(f"Spotify: {tool_args.get('command', 'control')}")
        else:
            actions.append(f"Executed {tool_name}")

        current_messages.append({
            "role": "tool",
            "name": tool_name,
            "content": tool_result,
        })

    return {
        **state,
        "tool_calls": [],
        "actions": actions,
        "messages": current_messages,
    }


async def respond_node(state: AgentState) -> AgentState:
    """Synthesize final voice-friendly reply following tool execution (tools=None to guarantee no loops)."""
    session_id = state["session_id"]
    current_messages = list(state.get("messages", []))

    # Ask model to speak natural-language confirmation based on tool observation
    completion = await get_completion(current_messages, tools=None)
    reply = str(completion)
    model_used = getattr(completion, "model_used", state.get("model_used", "ollama"))

    # Save completed turn into persistent conversation memory
    conversation_memory.add_message(session_id, "user", state["message"])
    conversation_memory.add_message(session_id, "assistant", reply)

    return {
        **state,
        "reply": reply,
        "model_used": model_used,
        "tool_calls": [],
    }


def _build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("chat", chat_node)
    graph.add_node("tools", tools_node)
    graph.add_node("respond", respond_node)

    graph.set_entry_point("chat")
    graph.add_conditional_edges("chat", should_call_tools, {"tools": "tools", END: END})
    graph.add_edge("tools", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


agent_graph = _build_graph()


async def run_agent(session_id: str, message: str) -> AgentState:
    return await agent_graph.ainvoke(
        {
            "session_id": session_id,
            "message": message,
            "reply": "",
            "model_used": "",
            "actions": [],
            "tool_calls": [],
            "messages": [],
        }
    )
