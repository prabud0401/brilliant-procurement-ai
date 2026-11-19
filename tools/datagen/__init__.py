"""Synthetic document generator package."""

from tools.datagen.generator import check_determinism_and_correctness, generate_documents
from tools.datagen.models import GroundTruth, ScenarioDocSpec
from tools.datagen.scenarios import get_all_scenarios

__all__ = [
    "GroundTruth",
    "ScenarioDocSpec",
    "check_determinism_and_correctness",
    "generate_documents",
    "get_all_scenarios",
]
