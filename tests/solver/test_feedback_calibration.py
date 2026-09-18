"""Offline feedback calibration guardrails. Traceability: H2, H3, H7, ADR-0028."""

from travel_agent.solver.feedback_calibration import (
    CalibrationEvidence,
    evaluate_weight_candidate,
)
from travel_agent.solver.itinerary_review import (
    DEFAULT_EXPERT_WEIGHT_PROFILE,
    ItineraryWeightProfile,
    ReviewDimension,
)


def _candidate(*, geography: int = 22, visit_value: int = 18) -> ItineraryWeightProfile:
    return ItineraryWeightProfile(
        "candidate-offline-v1",
        (
            (ReviewDimension.GEOGRAPHY, geography),
            (ReviewDimension.VISIT_VALUE, visit_value),
            (ReviewDimension.PACE, 15),
            (ReviewDimension.ROBUSTNESS, 15),
            (ReviewDimension.MEALS, 12),
            (ReviewDimension.FATIGUE, 8),
            (ReviewDimension.USER_INTENT, 10),
        ),
    )


def test_small_feedback_sample_cannot_change_production_weights() -> None:
    decision = evaluate_weight_candidate(
        DEFAULT_EXPERT_WEIGHT_PROFILE,
        _candidate(),
        CalibrationEvidence(8, 3, True, True, True, True),
    )

    assert not decision.eligible_for_release
    assert decision.rejection_reasons == (
        "insufficient_feedback_count",
        "insufficient_unique_users",
    )


def test_candidate_requires_bounded_delta_replay_and_human_approval() -> None:
    unbounded = evaluate_weight_candidate(
        DEFAULT_EXPERT_WEIGHT_PROFILE,
        _candidate(geography=24, visit_value=16),
        CalibrationEvidence(500, 200, True, False, True, False),
    )
    eligible = evaluate_weight_candidate(
        DEFAULT_EXPERT_WEIGHT_PROFILE,
        _candidate(),
        CalibrationEvidence(500, 200, True, True, True, True),
    )

    assert unbounded.rejection_reasons == (
        "weight_change_exceeds_limit",
        "adversarial_cases_failed",
        "human_approval_missing",
    )
    assert eligible.eligible_for_release
    assert eligible.rejection_reasons == ()
