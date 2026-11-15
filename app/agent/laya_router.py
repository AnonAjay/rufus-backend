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
    # OS & App launches (exclude 'open source', 'open question')
    r"\b(?:open|launch|start|run|close)\b.*?\b(?:app|chrome|browser|vscode|code|whatsapp|spotify|explorer|terminal|antigravity|notepad)\b",
    r"\b(?:open|launch|start)\s+(?!source\b|question\b|world\b|mind\b)[a-z0-9_\-\.]+",
    # WhatsApp messaging
    r"\b(?:send|whatsapp|text|message)\b.*?\b(?:to|saying|that)\b",
    r"\b(?:what\s+did\s+\w+\s+reply|check\s+whatsapp|whatsapp\s+message)\b",
    # Media & system controls (avoid bare 'spotify' in conversational context)
    r"\b(?:play|pause|resume|skip|mute|unmute)\b",
    r"\b(?:spotify|volume|brightness)\s+(?:up|down|to|\d+|track|song|playlist|music|percent)",
    r"\b(?:turn\s+(?:up|down)|set\s+(?:volume|brightness)|mute\s+(?:sound|system|volume))",
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
    r"^(?:what\s+is|who\s+is|why\s+is|how\s+does|how\s+do|explain|define|tell\s+me\s+what)\s+(?!my\s+screen)",
]

# Patterns specifically identifying pure conceptual / educational requests
CONCEPTUAL_PATTERNS = [
    r"^(?:explain|teach\s+me|what\s+is|what\s+are|how\s+does|how\s+do|why\s+is|why\s+are|define|describe|clarify|elaborate)\b",
    r"\b(?:photosynthesis|quantum|physics|biology|chemistry|history|philosophy|calculus|mathematics|gravity|evolution)\b",
    r"\b(?:concept|theory|principle|fundamentals?|mental\s+model|analogy|how\s+it\s+works)\b",
]

CODER_PATTERNS = [
    r"^(?:can\s+you\s+)?(?:give\s+me\s+code|write|implement|create|generate|refactor|debug|fix)\b",
    r"\b(?:give\s+me\s+code|sample\s+code|example\s+code|code\s+snippet|source\s+code|print\s*[\(\"'])\b",
    r"\b(?:python|rust|c\+\+|cpp|typescript|javascript|golang|java|html|css|sql|bash|powershell|regex)\b.*?\b(?:code|function|script|algorithm|query|class|program|method|struct|loop)\b",
    r"\b(?:code|function|class|method|async|await|struct|enum|trait|decorator|pointer|refactor|debug|traceback|syntax|compiler)\b",
    r"```|[{}<>;=]{2,}",
]

RESEARCHER_PATTERNS = [
    r"^(?:compare|synthesize|analyze|contrast)\b",
    r"\b(?:research|benchmark|benchmarks|trade-offs?|literature|state\s+of\s+the\s+art|sota)\b",
    r"\b(?:empirical|dataset|metrics|latency\s+vs\s+throughput|pros\s+and\s+cons|whitepaper|rfc|deep\s+dive)\b",
]


def detect_persona_heuristic(cleaned: str) -> PersonaIntent:
    """Classify the user utterance into a persona style using the 5-tier Priority Cascade."""
    if any(re.search(p, cleaned) for p in CODER_PATTERNS):
        return "coder"
    if any(re.search(p, cleaned) for p in RESEARCHER_PATTERNS):
        return "researcher"
    if any(re.search(p, cleaned) for p in CONCEPTUAL_PATTERNS):
        return "instructor"
    return "companion"


def classify_with_fallback(text: str) -> ClassificationResult:
    """Heuristic 5-Tier Priority Cascade when Laya is not installed or loading."""
    cleaned = text.strip().lower()

    has_action_verb = any(re.search(p, cleaned) for p in ACTION_PATTERNS)
    is_coding = any(re.search(p, cleaned) for p in CODER_PATTERNS)
    is_research = any(re.search(p, cleaned) for p in RESEARCHER_PATTERNS)
    is_conceptual = any(re.search(p, cleaned) for p in CONCEPTUAL_PATTERNS)

    # PRIORITY 1: Physical OS / Hardware Actions
    if has_action_verb:
        action_persona = "coder" if is_coding and "screen" in cleaned else "companion"
        return {
            "action_type": "action",
            "persona_intent": action_persona,
            "confidence": 0.95,
            "source": "cascade_priority_1_action",
            "reason": "Matched physical/OS hardware action trigger",
        }

    # PRIORITY 2: Code Artifacts & Programming (write, implement, debug, code snippets)
    if is_coding:
        return {
            "action_type": "speech",
            "persona_intent": "coder",
            "confidence": 0.95,
            "source": "cascade_priority_2_coder",
            "reason": "Matched coding/implementation request",
        }

    # PRIORITY 3: Comparative Research / Benchmarks / Literature Synthesis
    if is_research:
        return {
            "action_type": "speech",
            "persona_intent": "researcher",
            "confidence": 0.95,
            "source": "cascade_priority_3_researcher",
            "reason": "Matched comparative research/benchmark request",
        }

    # PRIORITY 4: Conceptual Learning / Pedagogy / First Principles
    if is_conceptual:
        return {
            "action_type": "speech",
            "persona_intent": "instructor",
            "confidence": 0.95,
            "source": "cascade_priority_4_instructor",
            "reason": "Matched foundational concept/pedagogy request",
        }

    # PRIORITY 5: Conversational Dialogue / Greetings / Banter
    return {
        "action_type": "speech",
        "persona_intent": "companion",
        "confidence": 0.90,
        "source": "cascade_priority_5_companion",
        "reason": "Defaulted to conversational companion dialogue",
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

                is_coding = any(re.search(p, cleaned) for p in CODER_PATTERNS)
                is_research = any(re.search(p, cleaned) for p in RESEARCHER_PATTERNS)

                # Invariant 1: Physical OS/hardware actions default to companion persona unless specifically coding
                if action_choice == "action" and not is_coding:
                    persona_choice = "companion"

                # Invariant 2: Pure conceptual, coding, or research inquiries without explicit OS verbs
                # must ALWAYS stay on the speech path to prevent unneeded tool calling.
                if (is_conceptual or is_coding or is_research) and not has_action_verb:
                    logger.info("Pure knowledge/coding utterance detected; forcing speech path.")
                    return {
                        "action_type": "speech",
                        "persona_intent": persona_choice,
                        "confidence": max(action_confidence, 0.92),
                        "source": "laya_intent_guard",
                        "reason": f"Pure knowledge inquiry routed to speech ({persona_choice} mode)",
                    }

                # Action safety threshold for ambiguous inputs
                if action_prob > 0.25 and action_choice == "speech" and not (is_conceptual or is_coding or is_research):
                    logger.info(
                        "Laya action probability %.2f > 0.25 on non-knowledge input; fail-safing to 'action'",
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

