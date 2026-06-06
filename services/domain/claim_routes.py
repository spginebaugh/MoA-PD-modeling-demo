"""Removed legacy structured-claim routing.

Claim interpretation is no longer a scenario router. It should produce pathway
graph operations through the predictor/composer boundary.
"""

from __future__ import annotations

CLAIM_ROUTES: tuple[object, ...] = ()
CLAIM_ROUTE_BY_KEY: dict[tuple[object, ...], object] = {}
SUPPORTED_STRUCTURED_CLAIM_KEYS: frozenset[tuple[object, ...]] = frozenset()
