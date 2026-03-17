from __future__ import annotations

from typing import List

from .schemas import MatchLabel, MatchResult, MatchSignals, MatcherConfig


def _weighted_score(signals: MatchSignals, config: MatcherConfig) -> float:
    values = {
        "upc_match": 1.0 if signals.upc_match else 0.0,
        "brand_match": 1.0 if signals.brand_match else 0.0,
        "model_match": 1.0 if signals.model_match else 0.0,
        "title_similarity": signals.title_similarity,
        "category_match": 1.0 if signals.category_match else 0.0,
        "semantic_similarity": signals.semantic_similarity,
        "image_similarity": signals.image_similarity,
    }
    score = 0.0
    total_weight = 0.0
    for key, weight in config.weights.items():
        value = values.get(key)
        if value is None:
            continue
        score += weight * float(value)
        total_weight += weight

    if total_weight == 0:
        return 0.0
    return score / total_weight


def _label(score: float, thresholds: dict[MatchLabel, float]) -> MatchLabel:
    if score >= thresholds["exact"]:
        return "exact"
    if score >= thresholds["probable"]:
        return "probable"
    if score >= thresholds["weak"]:
        return "weak"
    return "no_match"


def _explanation(signals: MatchSignals, label: MatchLabel) -> str:
    positives: List[str] = []
    negatives: List[str] = []

    if signals.upc_match:
        positives.append("UPC/EAN matched exactly")
    if signals.brand_match:
        positives.append("brand matched")
    if signals.model_match:
        positives.append("model/SKU aligned")
    if signals.title_similarity >= 0.8:
        positives.append("titles are highly similar")
    elif signals.title_similarity >= 0.6:
        positives.append("titles are moderately similar")

    if signals.variant_conflict:
        negatives.append("variant tokens conflict")
    if signals.brand_conflict:
        negatives.append("brand mismatch")

    if label == "no_match" and not positives:
        return "No strong product identifiers aligned across listing attributes."

    detail = ", ".join(positives[:3]) if positives else "limited shared signals"
    if negatives:
        return f"{detail}; caution: {', '.join(negatives[:2])}."
    return f"{detail}."


def score_match(signals: MatchSignals, config: MatcherConfig) -> MatchResult:
    """Generate confidence, label, and explanation from matching signals."""
    base_score = _weighted_score(signals, config)

    if signals.upc_match and (signals.brand_match or signals.model_match):
        base_score = max(base_score, 0.95)
    elif signals.upc_match:
        base_score = max(base_score, 0.88)

    if signals.brand_match and signals.model_match and signals.title_similarity >= 0.7:
        floor = 0.8 if signals.category_match else 0.72
        base_score = max(base_score, floor)

    if signals.brand_conflict:
        base_score -= config.brand_mismatch_penalty
    if signals.variant_conflict:
        base_score -= config.variant_mismatch_penalty

    confidence = min(1.0, max(0.0, round(base_score, 4)))
    label = _label(confidence, config.thresholds)

    return MatchResult(
        match_confidence=confidence,
        match_label=label,
        explanation=_explanation(signals, label),
        extracted_signals=signals.to_dict(),
    )
