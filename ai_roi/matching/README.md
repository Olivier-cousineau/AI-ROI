# AI-ROI Product Matching Module (Phase 2)

This module adds a production-oriented, explainable matching layer for EconoPlus.
It compares a retail product against a marketplace listing and returns:

- `match_confidence` in `[0, 1]`
- `match_label`: `exact | probable | weak | no_match`
- `explanation`: short rationale
- `extracted_signals`: structured matching signals

## Module structure

- `schemas.py` — typed schemas, result contracts, plugin interfaces
- `normalizer.py` — title/brand/model/category/identifier normalization
- `features.py` — matching signal extraction
- `scoring.py` — hybrid deterministic + weighted scoring
- `matcher.py` — public `ProductMatcher` orchestration

## Baseline matching logic

1. Normalize fields to reduce marketplace noise.
2. Compute core signals:
   - exact UPC/EAN compatibility
   - brand match
   - model/SKU match
   - title similarity (token + lexical)
   - optional semantic similarity plugin
   - category compatibility
   - optional image similarity plugin
3. Score using weighted aggregation + deterministic overrides for strong identifiers.
4. Apply penalties for clear mismatch clues (brand mismatch, likely variant conflict).

## Optional plugin interfaces

`schemas.py` defines pluggable protocols:

- `SemanticSimilarityProvider`
- `ImageSimilarityProvider`

These make it easy to add embeddings, CV models, or external services later without changing matcher core logic.

## Quick usage

```python
from ai_roi.matching import ProductMatcher

matcher = ProductMatcher()
result = matcher.match(
    {
        "title": "Apple AirPods Pro 2nd Gen with MagSafe Case",
        "brand": "Apple",
        "model": "A2698",
        "upc": "194253397168",
        "category": "Electronics > Headphones",
    },
    {
        "title": "Apple AirPods Pro (2nd Generation) A2698",
        "brand": "Apple",
        "model": "A2698",
        "ean": "194253397168",
        "category": "Electronics/Audio/Headphones",
    },
)

print(result.match_confidence, result.match_label, result.explanation)
print(result.extracted_signals)
```

## Next evolution path

- Train or fine-tune an ML ranker from labeled match outcomes.
- Add embedding-based semantic title/attribute similarity.
- Add LLM-based attribute extraction for messy listing titles.
- Add image similarity model for visual confirmation.
- Calibrate thresholds by category and condition segment.
