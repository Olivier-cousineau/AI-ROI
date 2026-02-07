"""High-precision eBay matching logic."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ai.match_utils import (
    MatchSignals,
    extract_title_tokens,
    has_brand_match,
    has_model_match,
    normalize_brand,
    normalize_model,
    normalize_title,
    normalize_upc,
    score_candidate,
    title_similarity,
)


@dataclass
class MatchResult:
    status: str
    confidence: float
    reason_codes: list[str]
    signals: MatchSignals
    query_used: str | None
    candidate: dict[str, Any] | None


def build_search_plan(deal_payload: dict[str, Any]) -> list[dict[str, str | None]]:
    brand = normalize_brand(deal_payload.get("brand") if isinstance(deal_payload, dict) else None)
    model_number = normalize_model(deal_payload.get("model_number") if isinstance(deal_payload, dict) else None)
    upc = normalize_upc(deal_payload.get("upc") if isinstance(deal_payload, dict) else None)
    title = deal_payload.get("title") if isinstance(deal_payload, dict) else None
    title_norm = normalize_title(title or "") if title else ""

    plan: list[dict[str, str | None]] = []
    if upc:
        plan.append({"pass": "A", "query": upc})
    if brand and model_number:
        plan.append({"pass": "B", "query": f"{brand} {model_number}".strip()})
    if title_norm:
        query = f"{brand} {title_norm}".strip() if brand else title_norm
        plan.append({"pass": "C", "query": query})
    return plan


def _image_match_score(deal_image: str | None, ebay_image: str | None, brand: str | None) -> float:
    if not deal_image or not ebay_image:
        return 0.0
    deal_tokens = extract_title_tokens(deal_image).get("tokens") or []
    ebay_tokens = extract_title_tokens(ebay_image).get("tokens") or []
    if not deal_tokens or not ebay_tokens:
        return 0.0
    overlap = len(set(deal_tokens) & set(ebay_tokens))
    union = len(set(deal_tokens) | set(ebay_tokens))
    score = overlap / union if union else 0.0
    if brand and brand in deal_tokens and brand in ebay_tokens:
        score = max(score, 0.8)
    return round(min(1.0, score), 4)


def _build_signals(
    deal_payload: dict[str, Any],
    candidate: dict[str, Any],
) -> MatchSignals:
    deal_brand = normalize_brand(deal_payload.get("brand") if isinstance(deal_payload, dict) else None)
    deal_model = normalize_model(deal_payload.get("model_number") if isinstance(deal_payload, dict) else None)
    deal_upc = normalize_upc(deal_payload.get("upc") if isinstance(deal_payload, dict) else None)
    deal_title = deal_payload.get("title") if isinstance(deal_payload, dict) else None
    deal_image = deal_payload.get("image") if isinstance(deal_payload, dict) else None

    candidate_title = candidate.get("title")
    candidate_brand = candidate.get("brand")
    candidate_upc = normalize_upc(candidate.get("upc") if isinstance(candidate, dict) else None)
    candidate_image = candidate.get("image")

    brand_match = has_brand_match(deal_brand, candidate_title, candidate_brand)
    model_exact, model_partial = has_model_match(deal_model, candidate_title)
    similarity = title_similarity(str(deal_title or ""), str(candidate_title or ""))
    upc_match = bool(deal_upc and candidate_upc and deal_upc == candidate_upc)
    image_score = _image_match_score(
        str(deal_image) if isinstance(deal_image, str) else None,
        str(candidate_image) if isinstance(candidate_image, str) else None,
        deal_brand,
    )
    return MatchSignals(
        brand_match=brand_match,
        model_match=model_partial,
        model_exact=model_exact,
        title_similarity=similarity,
        upc_match=upc_match,
        image_match=image_score >= 0.8,
        image_match_score=image_score,
    )


def match_ebay_candidates(
    deal_payload: dict[str, Any],
    candidates: list[dict[str, Any]],
    pass_label: str,
    query_used: str | None,
) -> MatchResult:
    if not candidates:
        return MatchResult(
            status="unmatched",
            confidence=0.0,
            reason_codes=["NO_CANDIDATES"],
            signals=MatchSignals(False, False, False, 0.0, False, False, 0.0),
            query_used=query_used,
            candidate=None,
        )

    reasons: list[str] = []
    scored: list[tuple[float, MatchSignals, dict[str, Any], list[str]]] = []
    deal_brand = normalize_brand(deal_payload.get("brand") if isinstance(deal_payload, dict) else None)
    deal_model = normalize_model(deal_payload.get("model_number") if isinstance(deal_payload, dict) else None)
    for candidate in candidates:
        signals = _build_signals(deal_payload, candidate)
        candidate_reasons: list[str] = []

        if pass_label == "A" and not signals.upc_match:
            candidate_reasons.append("REJECT_UPC_MISMATCH")
            continue
        if deal_brand and not signals.brand_match and not signals.upc_match:
            candidate_reasons.append("REJECT_BRAND_MISMATCH")
            continue
        if deal_model and not (signals.model_match or signals.model_exact) and not signals.upc_match:
            candidate_reasons.append("REJECT_MODEL_MISSING")
            continue
        if signals.title_similarity < 0.72 and not signals.upc_match:
            candidate_reasons.append("REJECT_TITLE_LOW")
            continue

        require_brand = pass_label in {"B", "C"}
        score = score_candidate(signals, require_brand=require_brand)
        if score <= 0:
            candidate_reasons.append("REJECT_SCORE_LOW")
            continue

        if signals.upc_match:
            candidate_reasons.append("UPC_EXACT")
        elif signals.brand_match and signals.model_exact:
            candidate_reasons.append("BRAND_MODEL_EXACT")
        elif pass_label == "C" and signals.title_similarity >= 0.72:
            candidate_reasons.append("FUZZY_TITLE_OK")

        scored.append((score, signals, candidate, candidate_reasons))

    if not scored:
        reasons.extend(["NO_VALID_CANDIDATES"])
        return MatchResult(
            status="unmatched",
            confidence=0.0,
            reason_codes=reasons,
            signals=MatchSignals(False, False, False, 0.0, False, False, 0.0),
            query_used=query_used,
            candidate=None,
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    top_score, top_signals, top_candidate, top_reasons = scored[0]
    if len(scored) > 1 and (top_score - scored[1][0]) <= 0.08:
        return MatchResult(
            status="ambiguous",
            confidence=top_score,
            reason_codes=["AMBIGUOUS_MATCH"],
            signals=top_signals,
            query_used=query_used,
            candidate=None,
        )

    is_perfect = top_signals.upc_match or (
        top_signals.brand_match and top_signals.model_exact and top_signals.title_similarity >= 0.80
    )
    if not is_perfect:
        return MatchResult(
            status="unmatched",
            confidence=top_score,
            reason_codes=top_reasons + ["NOT_PERFECT_MATCH"],
            signals=top_signals,
            query_used=query_used,
            candidate=None,
        )

    return MatchResult(
        status="matched",
        confidence=top_score,
        reason_codes=top_reasons,
        signals=top_signals,
        query_used=query_used,
        candidate=top_candidate,
    )
