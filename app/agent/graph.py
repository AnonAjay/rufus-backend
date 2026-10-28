import re
import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agent.emotion import get_current_emotion
from app.agent.hybrid_memory import hybrid_memory
from app.agent.llm_router import get_completion
from app.agent.memory import conversation_memory
from app.agent.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

def sanitize_reply(text: str) -> str:
    """Strip any leaked JSON tool-call payloads from model responses, even if truncated."""
    if not text:
        return ""

    t = text.strip()
    # Strip markdown code blocks containing json
    t = re.sub(r"```(?:json)?[\s\S]*?```", "", t).strip()

    # Strip leading colon/semicolon/punctuation spam (e.g. ::::::: )
    t = re.sub(r"^[:;,\.\s\-]+", "", t).strip()

    # Iteratively remove any JSON objects that contain tool calling indicators
    while True:
        start_idx = t.find("{")
        if start_idx == -1:
            break

        depth = 0
        end_idx = -1
        in_string = False
        escape = False

        for i in range(start_idx, len(t)):
            ch = t[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if not in_string:
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        end_idx = i
                        break

        if end_idx != -1:
            block = t[start_idx : end_idx + 1]
            if any(k in block for k in ['"name"', '"tool"', '"action"', '"arguments"', '"parameters"']):
                # Remove this complete JSON tool block
                t = (t[:start_idx] + t[end_idx + 1:]).strip()
                continue
            else:
                break
        else:
            # Unclosed / truncated JSON block cut off at token limit
            remaining = t[start_idx:]
            if any(k in remaining for k in ['"name"', '"tool"', '"action"', '"arguments"', '"parameters"']):
                t = t[:start_idx].strip()
            break

    # Strip any leftover punctuation spam
    t = re.sub(r"^[:;,\.\s\-]+", "", t).strip()
    return t

SYSTEM_PROMPT = (
    "You are Rufus, a companion robot dog and desktop assistant. Keep replies voice-friendly: "
    "use 1-3 short spoken sentences unless the user explicitly asks for more detail. "
    "Do not use markdown, bullet points, headers, or numbered lists because replies "
    "will be read aloud through text-to-speech. Ask at most one question per reply. "
    "You have access to tools to open discovered desktop applications (WhatsApp, VS Code, Chrome, Brave, Discord, Spotify, Antigravity, Explorer, etc.), "
    "send or draft WhatsApp messages, search WhatsApp contacts and chats, open websites, search the web / define concepts, "
    "control Spotify, adjust system volume, adjust screen brightness, visually inspect the screen with vision AI, and lock the workstation. "
    "When the user asks about anything on their screen, wants an app or error inspected, or asks for recommendations from open apps, "
    "you MUST call inspect_screen with their specific question in the query parameter. "
    "Never output raw JSON in your spoken reply. After an action executes, confirm it warmly in one short sentence."
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
    # Fetch Working Memory (capped to 10 turns to avoid 3B token bloat)
    history = hybrid_memory.get_working_memory(session_id, limit=10)

    # Clean history so no old JSON leaks into the prompt
    cleaned_history = []
    for m in history:
        clean_c = sanitize_reply(m["content"]) if m.get("role") in {"assistant", "rufus"} else m["content"]
        if clean_c:
            role = "assistant" if m.get("role") in {"assistant", "rufus"} else "user"
            cleaned_history.append({"role": role, "content": clean_c})

    current_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"Current observed user emotion: {emotion}."},
        *cleaned_history,
        {"role": "user", "content": user_message},
    ]

    try:
        completion = await get_completion(current_messages, tools=TOOL_DEFINITIONS)
    except TypeError:
        completion = await get_completion(current_messages)

    raw_reply = str(completion)
    model_used = getattr(completion, "model_used", "ollama")
    tool_calls = getattr(completion, "tool_calls", [])

    clean_content = sanitize_reply(raw_reply)
    if not clean_content and tool_calls:
        clean_content = f"Looking into that for you..."

    current_messages.append({"role": "assistant", "content": clean_content})

    # If no tools were called, this is the final conversational reply
    if not tool_calls:
        conversation_memory.add_message(session_id, "user", user_message)
        conversation_memory.add_message(session_id, "assistant", clean_content)
        hybrid_memory.save_turn(
            session_id=session_id,
            user_text=user_message,
            assistant_reply=clean_content,
            actions=[],
            model_used=model_used,
        )

    return {
        **state,
        "reply": clean_content,
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
        elif tool_name == "system_volume":
            actions.append(f"Volume: {tool_args.get('action', 'adjusted')}")
        elif tool_name == "screen_brightness":
            actions.append(f"Brightness: {tool_args.get('action', 'adjusted')}")
        elif tool_name in {"capture_screenshot", "inspect_screen"}:
            actions.append("Inspected Screen (Vision)")
        elif tool_name == "lock_workstation":
            actions.append("Locked Workstation")
        elif tool_name == "whatsapp_send_message":
            recipient = tool_args.get("recipient", "contact")
            actions.append(f"WhatsApp to {recipient.title()}")
        elif tool_name == "whatsapp_search_contacts":
            actions.append(f"Searched WhatsApp: {tool_args.get('query', '')}")
        elif tool_name == "whatsapp_list_messages":
            actions.append("Checked WhatsApp")
        else:
            actions.append(f"Executed {tool_name}")

        current_messages.append({
            "role": "user",
            "content": (
                f"[Tool observation from {tool_name}]: {tool_result}\n"
                "In 1 to 2 short, voice-friendly sentences, describe the findings and directly answer the user's question."
            ),
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
    reply = sanitize_reply(str(completion))
    if not reply:
        last_action = state.get("actions", ["your request"])[-1] if state.get("actions") else "your request"
        reply = f"I've completed {last_action} for you."

    model_used = getattr(completion, "model_used", state.get("model_used", "ollama"))

    # Save completed turn into persistent conversation memory
    conversation_memory.add_message(session_id, "user", state["message"])
    conversation_memory.add_message(session_id, "assistant", reply)
    hybrid_memory.save_turn(
        session_id=session_id,
        user_text=state["message"],
        assistant_reply=reply,
        actions=state.get("actions", []),
        model_used=model_used,
    )

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
