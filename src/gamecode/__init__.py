"""GameCode — locked-down 5-agent coding assistant."""

from .agents import (
    AGENT_ORDER,
    AGENT_SPECS,
    AgentManager,
    AgentResponse,
    AgentRole,
    AgentSpec,
    Guardrail,
    GuardrailResult,
    WHAT_NEXT_LINE,
    ANTI_JAILBREAK_BOILERPLATE,
)
from .guardrails import CPP_PATTERN, CS_PATTERN
from .handoff import HandoffContext, HandoffManager, TranscriptEntry
from .security import (
    AES256Cipher,
    DecryptionError,
    KeyDerivation,
    LicenseManager,
    PromptStore,
)

__version__ = "0.1.0"

__all__ = [
    "AES256Cipher", "DecryptionError", "KeyDerivation",
    "LicenseManager", "PromptStore",
    "AGENT_ORDER", "AGENT_SPECS", "AgentManager", "AgentResponse",
    "AgentRole", "AgentSpec", "Guardrail", "GuardrailResult",
    "WHAT_NEXT_LINE", "ANTI_JAILBREAK_BOILERPLATE",
    "CPP_PATTERN", "CS_PATTERN",
    "HandoffContext", "HandoffManager", "TranscriptEntry",
    "__version__",
]