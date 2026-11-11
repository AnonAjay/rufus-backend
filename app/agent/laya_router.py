"""
Laya-based System 1 Decision Router for Rufus Agent Core.

Uses Convai Innovations' Laya (ModernBERT-large decision model) to classify
incoming user utterances in a single forward pass without generating text.

Differentiates:
- 'speech': Conversational queries, greetings, general questions, chitchat.
  Routes to chat_node (LLM with tools=None) to eliminate tool hallucinations
  and optimize voice latency.
- 'action': OS application launches, WhatsApp messaging, Spotify/volume controls,
  vision screen inspections, robot physical stunts, timers.
  Routes to agent_node (LLM with tools=TOOL_DEFINITIONS).
"""
import logging
import re
from typing import Literal, TypedDict

logger = logging.getLogger(__name__)

ActionType = Literal["speech", "action"]
PersonaIntent = Literal["companion", "instructor", "researcher", "coder"]


class ClassificationResult(TypedDict):
    action_type: ActionType
    persona_intent: PersonaIntent
    confidence: float
    source: str
    reason: str


# Global singleton for the Laya Router instance
_laya_router = None
_laya_init_failed = False

DECISION_QUESTIONS = {
    "action_type": {
        "type": "choice",
        "instructions": (
            "Determine whether the user is asking Rufus to execute an external OS/hardware action or engage in conversational speech."
        ),
        "criteria": {
            "speech": (
                "Conversational dialogue, greetings, asking how Rufus is feeling, asking to tell a joke or story, "
                "answering general knowledge questions, giving advice, pedagogical explanations, conceptual questions, "
                "or verbal explanations without executing software."
            ),
            "action": (
                "Requests to open or close desktop applications, launch software, send a WhatsApp message, "
                "control Spotify or system volume, inspect the computer screen with vision, or trigger robot motor stunts."
            ),
        },
    },
    "persona_intent": {
        "type": "choice",
        "instructions": (
            "Determine the pedagogical, analytical, or stylistic persona best suited to address the user's utterance."
        ),
        "criteria": {
            "companion": (
                "Short everyday dialogue, greetings, casual banter, quick confirmations, desktop actions, or brief voice assistant queries."
            ),
            "instructor": (
                "In-depth conceptual explanations, 'explain what is', academic or scientific inquiries, learning how a mechanism works, or asking for teaching and analogies."
            ),
            "researcher": (
                "Technical literature reviews, comparative benchmarks, multi-perspective investigations, trade-off evaluations, citations, or empirical data synthesis."
            ),
            "coder": (
                "Programming questions, software architecture, debugging code, writing scripts, regex, data structures, algorithms, or API implementations."
            ),
        },
    },
}

# Fast regex patterns for resilient fallback
ACTION_PATTERNS = [
    # OS & App launches
    r"\b(?:open|launch|start|run|close)\b.*?\b(?:app|chrome|browser|vscode|code|whatsapp|spotify|explorer|terminal|antigravity|notepad)\b",
    r"\b(?:open|launch|start)\s+[a-z0-9_\-\.]+",
    # WhatsApp messaging
    r"\b(?:send|whatsapp|text|message)\b.*?\b(?:to|saying|that)\b",
    r"\b(?:what\s+did\s+\w+\s+reply|check\s+whatsapp|whatsapp\s+message)\b",
    # Media & system controls
    r"\b(?:play|pause|resume|skip|spotify|volume|mute|unmute|brightness)\b",
    # Vision & Screen inspection
    r"\b(?:inspect|screenshot|what'?s\s+on\s+(?:my\s+)?screen|look\s+at\s+(?:my\s+)?screen|read\s+(?:the\s+)?screen)\b",
    # Physical stunts / Robot movements
    r"\b(?:sit|stand|wag|backflip|dance|walk|bark|stunt|move)\b",
    # Productivity & Timers
    r"\b(?:set\s+(?:a\s+)?timer|start\s+(?:a\s+)?timer|focus\s+mode|pomodoro)\b",
    # System locks
    r"\b(?:lock\s+(?:my\s+)?(?:pc|computer|workstation|screen))\b",
]

SPEECH_PATTERNS = [
    r"^(?:hi|hello|hey|good\s+(?:morning|afternoon|evening)|howdy)\b",
    r"\b(?:how\s+are\s+you|who\s+are\s+you|what\s+is\s+your\s+name|tell\s+me\s+about\s+yourself)\b",
    r"\b(?:tell\s+me\s+a\s+joke|what\s+do\s+you\s+think\s+about|can\s+we\s+talk)\b",
    r"^(?:what\s+is|who\s+is|why\s+is|how\s+does|explain|define|tell\s+me\s+what)\s+(?!my\s+screen)",
]

# Patterns specifically identifying pure conceptual / educational requests
CONCEPTUAL_PATTERNS = [
    r"^(?:explain|teach\s+me|what\s+is|what\s+are|how\s+does|how\s+do|why\s+is|why\s+are|define|describe|clarify|elaborate)\b",
    r"\b(?:photosynthesis|quantum|physics|biology|chemistry|history|philosophy|calculus|mathematics|gravity|evolution)\b",
    r"\b(?:concept|theory|principle|fundamentals?|mental\s+model|analogy|how\s+it\s+works)\b",
]

CODER_PATTERNS = [
    r"\b(?:python|rust|c\+\+|typescript|javascript|golang|java|html|css|sql|bash|powershell|regex)\b",
    r"\b(?:code|function|class|method|async|await|struct|enum|trait|decorator|pointer|refactor|debug|traceback|syntax|compiler)\b",
    r"\b(?:api|endpoint|fastapi|react|tauri|langgraph|vite|pydantic|docker)\b",
    r"```|[{}<>;=]{2,}",
]

RESEARCHER_PATTERNS = [
    r"\b(?:research|benchmark|benchmarks|compare|comparison|trade-offs?|literature|state\s+of\s+the\s+art|sota)\b",
    r"\b(?:empirical|dataset|metrics|latency\s+vs\s+throughput|pros\s+and\s+cons|whitepaper|rfc|deep\s+dive)\b",
]


def detect_persona_heuristic(cleaned: str) -> PersonaIntent:
    """Classify the user utterance into a persona style using heuristic matching."""
    for pattern in CODER_PATTERNS:
        if re.search(pattern, cleaned):
            return "coder"

    for pattern in RESEARCHER_PATTERNS:
        if re.search(pattern, cleaned):
            return "researcher"

    for pattern in CONCEPTUAL_PATTERNS:
        if re.search(pattern, cleaned):
            return "instructor"

    return "companion"


def classify_with_fallback(text: str) -> ClassificationResult:
    """Heuristic rule-based fallback when Laya is not installed or loading."""
    cleaned = text.strip().lower()

    # Detect persona intent first
    persona_intent = detect_persona_heuristic(cleaned)

    # Check for pure conceptual / explanation queries first (these should NEVER route to action)
    has_action_verb = any(re.search(p, cleaned) for p in ACTION_PATTERNS)
    is_conceptual = any(re.search(p, cleaned) for p in CONCEPTUAL_PATTERNS)

    if is_conceptual and not has_action_verb:
        effective_intent = persona_intent if persona_intent in {"coder", "researcher"} else "instructor"
        return {
            "action_type": "speech",
            "persona_intent": effective_intent,
            "confidence": 0.95,
            "source": "heuristic_conceptual",
            "reason": f"Pure conceptual inquiry routed to speech ({effective_intent} mode)",
        }

    # Check action triggers
    for pattern in ACTION_PATTERNS:
        if re.search(pattern, cleaned):
            return {
                "action_type": "action",
                "persona_intent": persona_intent,
                "confidence": 0.95,
                "source": "heuristic_fallback",
                "reason": f"Matched action pattern: {pattern}",
            }

    # Check pure speech patterns
    for pattern in SPEECH_PATTERNS:
        if re.search(pattern, cleaned):
            return {
                "action_type": "speech",
                "persona_intent": persona_intent,
                "confidence": 0.90,
                "source": "heuristic_fallback",
                "reason": f"Matched speech pattern: {pattern}",
            }

    # Safety Invariant: Ambiguity defaults to "action" so the full LLM agent
    # with tools can evaluate the query and no user command is dropped.
    return {
        "action_type": "action",
        "persona_intent": persona_intent,
        "confidence": 0.51,
        "source": "heuristic_fallback",
        "reason": "Defaulted to action on ambiguity (safety invariant)",
    }


def classify_intent(text: str) -> ClassificationResult:
    """
    Classify user message into 'speech' vs 'action' AND persona tone
    using Laya's non-autoregressive decision model or heuristic fallback.
    """
    if not text or not text.strip():
        return {
            "action_type": "speech",
            "persona_intent": "companion",
            "confidence": 1.0,
            "source": "empty_input",
            "reason": "Empty text defaulted to speech",
        }

    cleaned = text.strip().lower()
    has_action_verb = any(re.search(p, cleaned) for p in ACTION_PATTERNS)
    is_conceptual = any(re.search(p, cleaned) for p in CONCEPTUAL_PATTERNS)

    global _laya_router, _laya_init_failed

    # Try Laya model
    if not _laya_init_failed:
        try:
            if _laya_router is None:
                from laya import Router
                logger.info("Initializing Laya System 1 Decision Router...")
                _laya_router = Router(preload=False)

            predictions = _laya_router.predict(text, DECISION_QUESTIONS)
            if predictions and isinstance(predictions, dict):
                answers = predictions.get("answers", {}) if isinstance(predictions.get("answers"), dict) else {}

                # 1. Parse Action Type Decision
                action_dec = answers.get("action_type") or predictions.get("action_type")
                action_choice = "speech"
                action_confidence = 0.85
                action_prob = 0.0

                if isinstance(action_dec, dict):
                    action_choice = action_dec.get("choice") or action_dec.get("value") or "speech"
                    scores = action_dec.get("probabilities", {})
                    action_confidence = float(action_dec.get("answer_confidence") or scores.get(action_choice, 0.85))
                    action_prob = float(scores.get("action", 0.0))

                # 2. Parse Persona Intent Decision
                persona_dec = answers.get("persona_intent") or predictions.get("persona_intent")
                persona_choice = detect_persona_heuristic(cleaned)
                if isinstance(persona_dec, dict):
                    candidate_persona = persona_dec.get("choice") or persona_dec.get("value")
                    if candidate_persona in {"companion", "instructor", "researcher", "coder"}:
                        persona_choice = candidate_persona

                # 3. Soft Guardrails
                # Invariant: Pure conceptual inquiries ("Explain photosynthesis") without explicit OS verbs
                # must ALWAYS stay on the speech path to prevent unneeded tool calling.
                if is_conceptual and not has_action_verb:
                    logger.info("Pure conceptual utterance detected; forcing speech path.")
                    effective_intent = persona_choice if persona_choice in {"coder", "researcher"} else "instructor"
                    return {
                        "action_type": "speech",
                        "persona_intent": effective_intent,
                        "confidence": max(action_confidence, 0.92),
                        "source": "laya_conceptual_guard",
                        "reason": f"Pure conceptual inquiry routed to speech ({effective_intent} mode)",
                    }

                # Action safety threshold for ambiguous inputs
                if action_prob > 0.25 and action_choice == "speech" and not is_conceptual:
                    logger.info(
                        "Laya action probability %.2f > 0.25 on non-conceptual input; fail-safing to 'action'",
                        action_prob,
                    )
                    return {
                        "action_type": "action",
                        "persona_intent": persona_choice,
                        "confidence": action_prob,
                        "source": "laya_guardrail",
                        "reason": f"Ambiguous speech with action_prob={action_prob:.2f}",
                    }

                if action_choice in {"speech", "action"}:
                    return {
                        "action_type": action_choice,
                        "persona_intent": persona_choice,
                        "confidence": action_confidence,
                        "source": "laya",
                        "reason": f"Laya decision: {action_choice}/{persona_choice} ({action_confidence:.2f})",
                    }
        except ImportError:
            _laya_init_failed = True
            logger.info("Laya package not installed; using resilient heuristic router.")
        except Exception as exc:
            logger.warning("Laya inference encountered error: %s; falling back to heuristic.", exc)

    return classify_with_fallback(text)

