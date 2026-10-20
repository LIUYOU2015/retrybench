"""RetryBench public API."""

from .benchmark import EpisodeResult, run_episode, run_matrix
from .model import EvidenceContract, PolicyName, Schedule, TaskSpec
from .evaluation import EvaluationResult, evaluate, public_cases, score_predictions

__all__ = [
    "EpisodeResult",
    "EvidenceContract",
    "PolicyName",
    "Schedule",
    "TaskSpec",
    "run_episode",
    "run_matrix",
    "EvaluationResult",
    "evaluate",
    "public_cases",
    "score_predictions",
]

__version__ = "0.2.0"

