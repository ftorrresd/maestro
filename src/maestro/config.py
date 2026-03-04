from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

StepSize = Union[str, int]


class SampleMetadata(BaseModel):
    model_config = ConfigDict(extra="allow")

    k_factor: float

    @field_validator("k_factor")
    @classmethod
    def _validate_k_factor(cls, value: float) -> float:
        if value <= 0.0:
            raise ValueError("'sample_metadata.k_factor' must be > 0.")
        return value


class EnergyCorrectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = "scale_pt_mass"
    pt_branch: str
    mass_branch: str
    suffix: str = "_corr"
    variations: list[str] = Field(default_factory=lambda: ["nominal"])
    correction_file: Optional[str] = None
    correction_name: Optional[str] = None
    inputs: dict[str, str] = Field(default_factory=dict)

    @field_validator("method", "pt_branch", "mass_branch", "suffix")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("correction fields must not be empty strings.")
        return stripped

    @field_validator("correction_file", "correction_name")
    @classmethod
    def _validate_optional_non_empty(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("optional correction fields must not be empty strings.")
        return stripped

    @field_validator("variations")
    @classmethod
    def _validate_variations(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("'variations' must contain at least one variation.")
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("'variations' entries must not be empty.")
        return cleaned


class EventWeightCorrectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = "event_weight_sf"
    weight_branch: str
    suffix: str = "_sf"
    variations: list[str] = Field(default_factory=lambda: ["nominal"])
    correction_file: Optional[str] = None
    correction_name: Optional[str] = None
    inputs: dict[str, str] = Field(default_factory=dict)

    @field_validator("method", "weight_branch", "suffix")
    @classmethod
    def _validate_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError(
                "event-weight correction fields must not be empty strings."
            )
        return stripped

    @field_validator("correction_file", "correction_name")
    @classmethod
    def _validate_optional_non_empty(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError(
                "optional event-weight correction fields must not be empty strings."
            )
        return stripped

    @field_validator("variations")
    @classmethod
    def _validate_variations(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("'variations' must contain at least one variation.")
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("'variations' entries must not be empty.")
        return cleaned


class SkimConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input: str
    output: str
    tree: str = "Events"
    step_size: StepSize = "100 MB"
    sample_metadata: SampleMetadata
    n_events: int = -1
    offset: int = 0
    triggers: list[str] = Field(default_factory=list)
    object_requirements: dict[str, int] = Field(default_factory=dict)
    keep_branches: list[str] = Field(default_factory=list)
    correctionlib_files: list[str] = Field(default_factory=list)
    energy_corrections: list[EnergyCorrectionConfig] = Field(default_factory=list)
    event_weight_correction: Optional[EventWeightCorrectionConfig] = None
    event_weight_corrections: list[EventWeightCorrectionConfig] = Field(
        default_factory=list
    )

    @field_validator("n_events")
    @classmethod
    def _validate_n_events(cls, value: int) -> int:
        if value < -1:
            raise ValueError("'n_events' must be -1 (all) or >= 0.")
        return value

    @field_validator("offset")
    @classmethod
    def _validate_offset(cls, value: int) -> int:
        if value < 0:
            raise ValueError("'offset' must be >= 0.")
        return value

    @field_validator("input", "output", "tree")
    @classmethod
    def _validate_non_empty_string(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("string value must not be empty.")
        return stripped

    @field_validator("step_size")
    @classmethod
    def _validate_step_size(cls, value: StepSize) -> StepSize:
        if isinstance(value, int):
            if value <= 0:
                raise ValueError("'step_size' integer value must be > 0.")
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("'step_size' string value must not be empty.")
            return stripped
        raise ValueError("'step_size' must be an integer or string.")

    @field_validator("object_requirements")
    @classmethod
    def _validate_object_requirements(
        cls,
        value: dict[str, int],
    ) -> dict[str, int]:
        for branch_name, min_count in value.items():
            if min_count < 0:
                raise ValueError(f"'object_requirements.{branch_name}' must be >= 0.")
        return value

    @field_validator("correctionlib_files")
    @classmethod
    def _validate_correctionlib_files(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("'correctionlib_files' entries must not be empty.")
        return cleaned


def validate_config_object(raw_config: Any) -> SkimConfig:
    try:
        return SkimConfig.model_validate(raw_config)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def load_config(config_path: Path) -> SkimConfig:
    with config_path.open("r", encoding="utf-8") as handle:
        raw_config = json.load(handle)
    return validate_config_object(raw_config)


def load_config_source(config_source: str) -> SkimConfig:
    config_path = Path(config_source)
    if config_path.exists():
        return load_config(config_path)

    try:
        raw_config = json.loads(config_source)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Config source is neither an existing file path nor valid JSON string."
        ) from exc
    return validate_config_object(raw_config)


def coerce_config(config: Union[SkimConfig, Mapping[str, Any]]) -> SkimConfig:
    if isinstance(config, SkimConfig):
        return config
    return SkimConfig.model_validate(dict(config))
