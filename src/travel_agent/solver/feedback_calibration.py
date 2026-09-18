"""Offline-only guardrails for future feedback-based weight calibration.

The production solve path never imports a candidate from user feedback. A
candidate becomes eligible for a later release only after enough independent
evidence, bounded changes, deterministic replay and explicit approval.

Traceability: H2, H3, H7, ADR-0028.
"""

from __future__ import annotations

from dataclasses import dataclass

from .itinerary_review import ItineraryWeightProfile


@dataclass(frozen=True, slots=True)
class CalibrationEvidence:
    feedback_count: int
    unique_user_count: int
    golden_cases_passed: bool
    adversarial_cases_passed: bool
    expert_replay_passed: bool
    human_approved: bool


@dataclass(frozen=True, slots=True)
class CalibrationDecision:
    eligible_for_release: bool
    rejection_reasons: tuple[str, ...]


def evaluate_weight_candidate(
    current: ItineraryWeightProfile,
    candidate: ItineraryWeightProfile,
    evidence: CalibrationEvidence,
    *,
    minimum_feedback_count: int = 200,
    minimum_unique_users: int = 80,
    maximum_dimension_change: int = 3,
) -> CalibrationDecision:
    """Validate an offline candidate; this function never activates it."""

    if minimum_feedback_count <= 0 or minimum_unique_users <= 0:
        raise ValueError("calibration sample thresholds must be positive")
    if maximum_dimension_change <= 0:
        raise ValueError("maximum dimension change must be positive")
    reasons = []
    if evidence.feedback_count < minimum_feedback_count:
        reasons.append("insufficient_feedback_count")
    if evidence.unique_user_count < minimum_unique_users:
        reasons.append("insufficient_unique_users")
    current_weights = dict(current.weights)
    if any(
        abs(weight - current_weights[dimension]) > maximum_dimension_change
        for dimension, weight in candidate.weights
    ):
        reasons.append("weight_change_exceeds_limit")
    if not evidence.golden_cases_passed:
        reasons.append("golden_cases_failed")
    if not evidence.adversarial_cases_passed:
        reasons.append("adversarial_cases_failed")
    if not evidence.expert_replay_passed:
        reasons.append("expert_replay_failed")
    if not evidence.human_approved:
        reasons.append("human_approval_missing")
    return CalibrationDecision(not reasons, tuple(reasons))
