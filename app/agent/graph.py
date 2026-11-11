import re
import logging
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.agent.emotion import get_current_emotion
from app.agent.hybrid_memory import hybrid_memory
from app.agent.laya_router import classify_intent
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

# ---------------------------------------------------------------------------
# Persona System Prompts Matrix
# ---------------------------------------------------------------------------
SHARED_TOOL_CAPABILITIES = (
    "You have access to tools to open discovered desktop applications (WhatsApp, VS Code, Chrome, Brave, Discord, Spotify, Antigravity, Explorer), "
    "send WhatsApp messages, check replies via whatsapp_get_last_interaction, search contacts, save contact numbers, open websites, search the web / define concepts, "
    "control Spotify, adjust system volume and brightness, visually inspect the screen with vision AI, and lock the workstation. "
    "When the user asks what someone replied or asks about WhatsApp messages, call whatsapp_get_last_interaction. "
    "When the user asks about anything on their screen, wants an open app or error inspected, or asks to read from display, "
    "you MUST call inspect_screen with their specific question in the query parameter. "
    "Never output raw JSON in your spoken reply."
)

PERSONA_PROMPTS: dict[str, str] = {
    # 1. Desktop Companion (Default: Voice-friendly, warm, concise, punchy)
    "companion": (
        "You are Rufus, an embodied AI companion robot dog and desktop assistant. "
        "Keep replies voice-friendly: use 1-3 short spoken sentences unless the user explicitly asks for more detail. "
        "Do not use markdown, bullet points, headers, or numbered lists because replies will be read aloud through text-to-speech. "
        "Ask at most one question per reply. After an action executes, confirm it warmly in one short sentence.\n\n"
        + SHARED_TOOL_CAPABILITIES
    ),
    # 2. Instructor (Pedagogical tutor, first-principles, citations, Socratic check)
    "instructor": (
        "You are Rufus in Instructor Mode—a master pedagogical tutor and technical educator. "
        "Your goal is deep conceptual clarity and teaching excellence.\n"
        "Guidelines:\n"
        "1. Break topics down systematically into foundational first principles.\n"
        "2. Use clear analogies, mental models, and real-world system architecture examples.\n"
        "3. Provide authoritative citations, academic references, RFCs, and official documentation links where relevant.\n"
        "4. Conclude with a sharp Socratic recall check question to verify the user's understanding.\n"
        "Format your responses cleanly with Markdown headers, bold highlights, and structured bullet points.\n\n"
        + SHARED_TOOL_CAPABILITIES
    ),
    # 3. Researcher (Evidence-driven synthesis, literature analysis, structured reports)
    "researcher": (
        "You are Rufus in Researcher Mode—an evidence-driven technical research analyst and literature synthesizer. "
        "Your goal is rigorous, objective, and multi-perspective technical investigation.\n"
        "Guidelines:\n"
        "1. Synthesize multi-source technical findings, contrasting trade-offs, state-of-the-art benchmarks, and empirical data.\n"
        "2. Highlight concrete facts, failure modes, scalability limits, and theoretical invariants.\n"
        "3. Structure output in professional Markdown reports with executive summaries, comparative tables, and cited findings.\n"
        "4. Maintain a neutral, precise, and intellectually honest tone with zero marketing hype or filler.\n"
        "Use web_search and screen inspection tools actively to gather empirical ground truth when needed.\n\n"
        + SHARED_TOOL_CAPABILITIES
    ),
    # 4. Coding Assistant (Elite systems engineer, code-centric, terse, zero filler)
    "coder": (
        "You are Rufus in Coding Assistant Mode—an elite systems programmer, full-stack engineer, and software architect. "
        "Your goal is production-grade code correctness, architectural durability, and high performance.\n"
        "Guidelines:\n"
        "1. Terse, direct, and code-centric. Skip conversational pleasantries, filler phrases, and generic introductions.\n"
        "2. Write idiomatic, production-ready code blocks with complete syntax highlighting, strict types, and robust error handling.\n"
        "3. Surface subtle edge cases, race conditions, memory leaks, security vulnerabilities, and typing pitfalls immediately.\n"
        "4. Explain architectural choices bluntly: why this approach over alternatives, what could break, and which file to inspect first.\n\n"
        + SHARED_TOOL_CAPABILITIES
    ),
}

def get_system_prompt(persona: str = "companion") -> str:
    """Retrieve the specialized system prompt for the specified persona."""
    return PERSONA_PROMPTS.get(persona, PERSONA_PROMPTS["companion"])


SYSTEM_PROMPT = PERSONA_PROMPTS["companion"]


class AgentState(TypedDict):
    session_id: str
    message: str
    persona: str
    reply: str
    model_used: str
    action_type: str
    confidence: float
    actions: list[str]
    tool_calls: list[dict]
    messages: list[dict]


async def router_node(state: AgentState) -> AgentState:
    """
    System 1 Intent Router powered by Laya (ModernBERT-large decision model).
    Runs in a single non-autoregressive forward pass to separate 'speech' vs 'action'
    and predict the appropriate pedagogical/analytical persona.
    """
    user_message = state["message"]
    classification = classify_intent(user_message)
    action_type = classification["action_type"]
    persona_intent = classification.get("persona_intent", "companion")
    confidence = float(classification.get("confidence", 0.95))

    # Resolve effective persona:
    # If the user locked a specific persona in the UI (not "auto"), honor their manual lock.
    # If persona is "auto" or empty, adopt Laya's predicted persona intent.
    requested_persona = state.get("persona", "auto")
    if requested_persona in {"companion", "instructor", "researcher", "coder"}:
        effective_persona = requested_persona
    else:
        effective_persona = persona_intent

    logger.info(
        "Laya router classified intent: action=%s, persona=%s (effective=%s, confidence=%.2f, source=%s, reason=%s)",
        action_type,
        persona_intent,
        effective_persona,
        confidence,
        classification.get("source", "unknown"),
        classification.get("reason", ""),
    )

    return {
        **state,
        "action_type": action_type,
        "confidence": confidence,
        "persona": effective_persona,
    }


def route_after_router(state: AgentState) -> str:
    """Conditional edge branching between speech conversation and action execution."""
    if state.get("action_type") == "speech":
        return "chat"
    return "agent"


async def chat_node(state: AgentState) -> AgentState:
    """
    Fast conversational speech node (invoked with tools=None).
    Guarantees zero tool hallucinations and minimal prefill latency for chit-chat.
    """
    session_id = state["session_id"]
    user_message = state["message"]
    emotion = get_current_emotion(session_id)
    history = hybrid_memory.get_working_memory(session_id, limit=10)

    cleaned_history = []
    for m in history:
        clean_c = sanitize_reply(m["content"]) if m.get("role") in {"assistant", "rufus"} else m["content"]
        if clean_c:
            role = "assistant" if m.get("role") in {"assistant", "rufus"} else "user"
            cleaned_history.append({"role": role, "content": clean_c})

    persona = state.get("persona", "companion")
    system_prompt = get_system_prompt(persona)

    current_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": f"Current observed user emotion: {emotion}."},
        *cleaned_history,
        {"role": "user", "content": user_message},
    ]

    completion = await get_completion(current_messages, tools=None)
    raw_reply = str(completion)
    model_used = getattr(completion, "model_used", "ollama")

    clean_content = sanitize_reply(raw_reply)
    if not clean_content:
        clean_content = "I'm right here with you! What's on your mind?"

    current_messages.append({"role": "assistant", "content": clean_content})

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
        "tool_calls": [],
        "messages": current_messages,
        "actions": list(state.get("actions", [])),
    }


async def agent_node(state: AgentState) -> AgentState:
    """
    Full action deliberation node (invoked with tools=TOOL_DEFINITIONS).
    Evaluates OS actions, WhatsApp, Spotify, screen vision, and robot stunts.
    """
    session_id = state["session_id"]
    user_message = state["message"]
    emotion = get_current_emotion(session_id)
    history = hybrid_memory.get_working_memory(session_id, limit=10)

    cleaned_history = []
    for m in history:
        clean_c = sanitize_reply(m["content"]) if m.get("role") in {"assistant", "rufus"} else m["content"]
        if clean_c:
            role = "assistant" if m.get("role") in {"assistant", "rufus"} else "user"
            cleaned_history.append({"role": role, "content": clean_c})

    persona = state.get("persona", "companion")
    system_prompt = get_system_prompt(persona)

    current_messages = [
        {"role": "system", "content": system_prompt},
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
        clean_content = "Looking into that for you..."

    current_messages.append({"role": "assistant", "content": clean_content})

    # If no tools were called in the action path, finalize conversational turn
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
            app_name = str(tool_args.get("app_name", "Application")).strip()
            actions.append(f"Opened {app_name.title()}")
        elif tool_name == "open_website":
            url = str(tool_args.get("url", "website")).strip()
            display_url = re.sub(r"^https?://(?:www\.)?", "", url).rstrip("/")
            actions.append(f"Navigated to {display_url}")
        elif tool_name == "web_search":
            query = str(tool_args.get("query", "")).strip()
            actions.append(f"Searched web for '{query}'" if query else "Searched web")
        elif tool_name == "spotify_control":
            cmd = str(tool_args.get("command", "control")).strip()
            target = str(tool_args.get("target", "")).strip()
            if target:
                actions.append(f"Spotify: {cmd.title()} '{target}'")
            else:
                actions.append(f"Spotify: {cmd.title()}")
        elif tool_name == "system_volume":
            val = tool_args.get("value")
            act = str(tool_args.get("action", "adjusted")).strip()
            if val is not None:
                actions.append(f"Set system volume to {val}%")
            else:
                actions.append(f"Adjusted system volume ({act})")
        elif tool_name == "screen_brightness":
            val = tool_args.get("value")
            if val is not None:
                actions.append(f"Set brightness to {val}%")
            else:
                actions.append("Adjusted screen brightness")
        elif tool_name in {"capture_screenshot", "inspect_screen"}:
            actions.append("Inspected screen with Vision AI")
        elif tool_name == "lock_workstation":
            actions.append("Locked Windows desktop")
        elif tool_name == "whatsapp_send_message":
            recipient = str(tool_args.get("recipient", "contact")).strip()
            actions.append(f"Sent text to {recipient.title()} on WhatsApp")
        elif tool_name == "whatsapp_get_last_interaction":
            contact = str(tool_args.get("contact", "contact")).strip()
            actions.append(f"Read {contact.title()}'s reply on WhatsApp")
        elif tool_name == "whatsapp_search_contacts":
            query = str(tool_args.get("query", "")).strip()
            actions.append(f"Searched WhatsApp contacts for {query.title()}" if query else "Searched WhatsApp contacts")
        elif tool_name == "whatsapp_list_messages":
            actions.append("Checked recent messages on WhatsApp")
        elif tool_name == "whatsapp_save_contact":
            name = str(tool_args.get("name", "Contact")).strip()
            actions.append(f"Saved {name.title()}'s contact on WhatsApp")
        elif tool_name == "robot_stunt":
            stunt = str(tool_args.get("stunt", "stunt")).strip()
            actions.append(f"Executed robot stunt: {stunt.title()}")
        else:
            clean_name = tool_name.replace("_", " ").title()
            actions.append(f"Executed {clean_name}")

        persona = state.get("persona", "companion")
        if persona == "instructor":
            instruction = (
                "Synthesize these findings thoroughly for the student. Break down core principles, "
                "provide conceptual depth and clear explanations, and conclude with a Socratic check question."
            )
        elif persona == "researcher":
            instruction = (
                "Synthesize these findings into an objective, evidence-driven technical summary with citations and key facts."
            )
        elif persona == "coder":
            instruction = (
                "Provide a concise, code-centric answer with production-ready snippets and edge case analysis."
            )
        else:
            instruction = (
                "In 1 to 2 short, voice-friendly sentences, describe the findings and directly answer the user's question."
            )

        current_messages.append({
            "role": "user",
            "content": f"[Tool observation from {tool_name}]: {tool_result}\n{instruction}",
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
        persona = state.get("persona", "companion")
        last_action = state.get("actions", ["your request"])[-1] if state.get("actions") else "your request"
        if persona in {"instructor", "researcher", "coder"}:
            # Find the last tool observation to avoid robotic companion fallback
            last_obs = ""
            for m in reversed(current_messages):
                if m.get("role") == "user" and "[Tool observation from" in m.get("content", ""):
                    last_obs = m["content"]
                    break
            if last_obs and "]: " in last_obs:
                obs_body = last_obs.split("]: ", 1)[-1].split("\n")[0]
                reply = f"Regarding {last_action}:\n\n{obs_body}"
            else:
                reply = f"I've completed {last_action}."
        else:
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
    graph.add_node("router", router_node)
    graph.add_node("chat", chat_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tools_node)
    graph.add_node("respond", respond_node)

    # 1. Entry Point: System 1 Decision Router (Laya)
    graph.set_entry_point("router")

    # 2. Branching: Pure speech skips tools; action requests deliberate with tools
    graph.add_conditional_edges(
        "router",
        route_after_router,
        {"chat": "chat", "agent": "agent"},
    )

    # 3. Speech Path: Directly concludes to END (zero tool hallucination)
    graph.add_edge("chat", END)

    # 4. Action Path: Executes tools if emitted; otherwise finishes to END
    graph.add_conditional_edges(
        "agent",
        should_call_tools,
        {"tools": "tools", END: END},
    )
    graph.add_edge("tools", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


agent_graph = _build_graph()


async def run_agent(session_id: str, message: str, persona: str = "companion") -> AgentState:
    return await agent_graph.ainvoke(
        {
            "session_id": session_id,
            "message": message,
            "persona": persona,
            "reply": "",
            "model_used": "",
            "action_type": "",
            "confidence": 0.95,
            "actions": [],
            "tool_calls": [],
            "messages": [],
        }
    )
