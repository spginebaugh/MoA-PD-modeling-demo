"""Shared Pydantic configuration and scalar aliases."""

from __future__ import annotations

from typing import Annotated

from pydantic import ConfigDict, Field

STRICT_MODEL_CONFIG = ConfigDict(extra="forbid", frozen=True)

Probability = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeFloat = Annotated[float, Field(ge=0.0)]

type JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
