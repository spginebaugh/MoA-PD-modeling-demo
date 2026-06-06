"""Small reusable validation helpers for domain model validators."""

from __future__ import annotations

from collections import Counter
from collections.abc import Container, Hashable, Iterable


def duplicate_items[T: Hashable](items: Iterable[T]) -> tuple[T, ...]:
    counts = Counter(items)
    return tuple(sorted((item for item, count in counts.items() if count > 1), key=str))


def missing_items[T](items: Iterable[T], known: Container[T]) -> tuple[T, ...]:
    return tuple(item for item in items if item not in known)
