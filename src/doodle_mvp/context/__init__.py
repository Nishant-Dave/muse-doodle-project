"""Context subpackage: desktop-state awareness and adaptive personality."""

from .model import ContextSnapshot, DesktopActivity, DoodleInteraction, FocusPhase
from .policy import ActivityLevel, PersonalityPolicy, PolicyDecision
from .store import ContextStore

__all__ = [
    "ActivityLevel",
    "ContextSnapshot",
    "ContextStore",
    "DesktopActivity",
    "DoodleInteraction",
    "FocusPhase",
    "PersonalityPolicy",
    "PolicyDecision",
]
