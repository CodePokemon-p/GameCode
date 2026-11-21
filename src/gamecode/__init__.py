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
)
from .security import (
    AES256Cipher,
    DecryptionError,
    KeyDerivation,
    LicenseManager,
    PromptStore,
)

__version__ = "0.1.0"

__all__ = [
    # security
    "AES256Cipher", "DecryptionError", "KeyDerivation",
    "LicenseManager", "PromptStore",
    # agents
    "AGENT_ORDER", "AGENT_SPECS", "AgentManager", "AgentResponse",
    "AgentRole", "AgentSpec", "Guardrail", "GuardrailResult",
    "__version__",
]