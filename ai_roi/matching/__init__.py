"""Modular product matching package for AI-ROI."""

from .matcher import ProductMatcher
from .schemas import MatchResult, MatcherConfig, ProductRecord

__all__ = ["ProductMatcher", "ProductRecord", "MatcherConfig", "MatchResult"]
