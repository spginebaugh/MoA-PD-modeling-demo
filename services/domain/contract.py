"""Generic display option helpers.

Pathway contracts are defined in services.pathway.models. This module remains
only for callers that need a tiny value/label option type.
"""

from __future__ import annotations

from pydantic import BaseModel

from .base import STRICT_MODEL_CONFIG


class DisplayOption(BaseModel):
    model_config = STRICT_MODEL_CONFIG

    value: str
    label: str


def option(value: str, label: str) -> DisplayOption:
    return DisplayOption(value=value, label=label)
