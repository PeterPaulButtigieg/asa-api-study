import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from fastapi import Request, Response
from pydantic import BaseModel, TypeAdapter, ValidationError

from app.accessibility import AccessibilityAnnotation, LinkDefinition
from app.dtos.common_dtos import AccessibilityDTO, AccessibilityNudgeDTO, LinkDTO


ACCESSIBILITY_HEADER_ALIAS = "Accessibility"
ACCESSIBILITY_HEADER_DESCRIPTION = "Set to true to include WCAG 2.2 accessibility nudges when enabled in the current environment."
WCAG_STANDARD = "WCAG 2.2"
WCAG_CRITERION_BASE_URL = "https://www.w3.org/TR/WCAG22/#"
WCAG_JSON_PATH = Path(__file__).resolve().parent.parent / "static" / "wcag.json"
LOCATION_PREFIXES_TO_SKIP = {"body", "query", "path", "header", "cookie"}
APP_ENVIRONMENT_VARIABLE = "APP_ENV"
ACCESSIBILITY_ENABLED_VARIABLE = "ACCESSIBILITY_NUDGES_ENABLED"
_BOOLEAN_ADAPTER = TypeAdapter(bool)


@dataclass(frozen=True)
class NudgeSeed:
    criterion_number: str
    type: str
    message: str
    target: str
    values: list[str] | None = None


@lru_cache(maxsize=1)
def load_wcag_index() -> dict[str, dict[str, Any]]:
    with WCAG_JSON_PATH.open("r", encoding="utf-8") as wcag_file:
        wcag_payload = json.load(wcag_file)
    wcag_index: dict[str, dict[str, Any]] = {}
    for principle in wcag_payload["principles"]:
        for guideline in principle["guidelines"]:
            for criterion in guideline["successcriteria"]:
                wcag_index[criterion["num"]] = criterion
    return wcag_index


def get_wcag_criterion(criterion_number: str) -> dict[str, Any]:
    wcag_index = load_wcag_index()
    try:
        return wcag_index[criterion_number]
    except KeyError as error:
        raise ValueError(f"WCAG success criterion {criterion_number} was not found in {WCAG_JSON_PATH}") from error


def accessibility_available() -> bool:
    explicit_setting = os.getenv(ACCESSIBILITY_ENABLED_VARIABLE)
    if explicit_setting is not None:
        try:
            return _BOOLEAN_ADAPTER.validate_python(explicit_setting)
        except ValidationError:
            return False
    return os.getenv(APP_ENVIRONMENT_VARIABLE, "development").lower() != "production"


def is_accessibility_enabled(request: Request) -> bool:
    if not accessibility_available():
        return False
    raw_header_value = request.headers.get(ACCESSIBILITY_HEADER_ALIAS)
    if raw_header_value is None:
        return False
    try:
        return _BOOLEAN_ADAPTER.validate_python(raw_header_value)
    except ValidationError:
        return False


def append_accessibility_vary_header(response: Response) -> None:
    if not accessibility_available():
        return
    existing_vary = response.headers.get("Vary")
    if existing_vary is None:
        response.headers["Vary"] = ACCESSIBILITY_HEADER_ALIAS
        return
    vary_values = [vary_value.strip() for vary_value in existing_vary.split(",") if vary_value.strip()]
    if ACCESSIBILITY_HEADER_ALIAS.lower() not in {vary_value.lower() for vary_value in vary_values}:
        vary_values.append(ACCESSIBILITY_HEADER_ALIAS)
    response.headers["Vary"] = ", ".join(vary_values)


def build_link_dtos(link_definitions: Sequence[LinkDefinition]) -> list[LinkDTO]:
    return [LinkDTO(href=link.href, rel=link.rel, type=link.type, label=link.label) for link in link_definitions]


def create_nudge_seed(
    criterion_number: str,
    nudge_type: str,
    message: str,
    target: str,
    values: list[str] | None = None,
) -> NudgeSeed:
    return NudgeSeed(criterion_number=criterion_number, type=nudge_type, message=message, target=target, values=values)


def _extract_annotation_values(annotation: AccessibilityAnnotation, value: Any, context: Any | None) -> list[str] | None:
    if annotation.values_resolver is None:
        return None
    values = annotation.values_resolver(value, context)
    if values is None:
        return None
    normalized_values: list[str] = []
    for item in values:
        normalized_item = str(item)
        if normalized_item not in normalized_values:
            normalized_values.append(normalized_item)
    return normalized_values or None


def _collect_model_nudge_seeds(data: BaseModel | list[BaseModel], path_prefix: str = "data") -> list[NudgeSeed]:
    if isinstance(data, list):
        seeds: list[NudgeSeed] = []
        for index, item in enumerate(data):
            seeds.extend(_collect_model_nudge_seeds(item, path_prefix=f"{path_prefix}[{index}]"))
        return seeds

    seeds: list[NudgeSeed] = []
    for field_name, model_field in data.__class__.model_fields.items():
        value = getattr(data, field_name)
        target = f"{path_prefix}.{field_name}"
        for annotation in model_field.metadata:
            if isinstance(annotation, AccessibilityAnnotation):
                seeds.append(
                    create_nudge_seed(
                        criterion_number=annotation.sc,
                        nudge_type=annotation.type.value,
                        message=annotation.message,
                        target=target,
                        values=_extract_annotation_values(annotation, value, data),
                    )
                )
        if isinstance(value, BaseModel):
            seeds.extend(_collect_model_nudge_seeds(value, path_prefix=target))
        elif isinstance(value, list) and value and all(isinstance(item, BaseModel) for item in value):
            for index, item in enumerate(value):
                seeds.extend(_collect_model_nudge_seeds(item, path_prefix=f"{target}[{index}]"))
    return seeds


def _collect_link_nudge_seeds(link_definitions: Sequence[LinkDefinition], path_prefix: str = "links") -> list[NudgeSeed]:
    seeds: list[NudgeSeed] = []
    for link in link_definitions:
        target = f"{path_prefix}[rel={link.rel}].label"
        for annotation in link.accessibility:
            seeds.append(
                create_nudge_seed(
                    criterion_number=annotation.sc,
                    nudge_type=annotation.type.value,
                    message=annotation.message,
                    target=target,
                    values=_extract_annotation_values(annotation, link.label, link),
                )
            )
    return seeds


def build_accessibility_response(
    data: BaseModel | list[BaseModel] | None = None,
    links: Sequence[LinkDefinition] | None = None,
    additional_nudge_seeds: Sequence[NudgeSeed] | None = None,
) -> AccessibilityDTO | None:
    seeds: list[NudgeSeed] = []
    if data is not None:
        seeds.extend(_collect_model_nudge_seeds(data))
    if links is not None:
        seeds.extend(_collect_link_nudge_seeds(links))
    if additional_nudge_seeds is not None:
        seeds.extend(additional_nudge_seeds)
    if not seeds:
        return None

    grouped_nudges: dict[tuple[str, str, str], dict[str, Any]] = {}
    for seed in seeds:
        key = (seed.criterion_number, seed.type, seed.message)
        grouped_nudges.setdefault(key, {"targets": [], "values": []})
        if seed.target not in grouped_nudges[key]["targets"]:
            grouped_nudges[key]["targets"].append(seed.target)
        for value in seed.values or []:
            if value not in grouped_nudges[key]["values"]:
                grouped_nudges[key]["values"].append(value)

    nudges: list[AccessibilityNudgeDTO] = []
    for (criterion_number, nudge_type, message), grouped in grouped_nudges.items():
        criterion = get_wcag_criterion(criterion_number)
        nudges.append(
            AccessibilityNudgeDTO(
                success_criterion=f"{criterion['num']} - {criterion['handle']}",
                level=criterion["level"],
                target=grouped["targets"],
                type=nudge_type,
                message=message,
                values=grouped["values"] or None,
                details=f"{WCAG_CRITERION_BASE_URL}{criterion['id']}",
            )
        )
    return AccessibilityDTO(standard=WCAG_STANDARD, nudges=nudges)


def to_readable_error_field(location: Sequence[object]) -> str:
    field_path: list[str] = []
    for part in location:
        if isinstance(part, str) and part in LOCATION_PREFIXES_TO_SKIP:
            continue
        if isinstance(part, int):
            if field_path:
                field_path[-1] = f"{field_path[-1]}[{part}]"
            else:
                field_path.append(f"[{part}]")
            continue
        field_path.append(str(part))
    return ".".join(field_path)


def get_validation_suggestion(field: str, error: dict[str, Any]) -> str | None:
    error_type = error["type"]
    error_context = error.get("ctx", {})
    if error_type == "missing":
        return "Provide a value for this field."
    field_specific_suggestions = {
        "customer.email": "Enter a valid email address, for example name@example.com.",
        "payment.expiry_date": "Enter the expiry date in MM/YY format, for example 12/30.",
        "payment.security_code": "Enter a three or four digit security code.",
        "payment.card_number": "Enter the complete test card number. Use 4242 4242 4242 4242 for success.",
        "product_id": "Use a product ID returned by GET /api/v1/products.",
        "quantity": "Enter a whole number within the allowed range.",
    }
    if field in field_specific_suggestions:
        return field_specific_suggestions[field]
    if error_type == "string_too_short":
        minimum_length = error_context.get("min_length")
        if minimum_length is not None:
            return f"Use at least {minimum_length} character{'' if minimum_length == 1 else 's'}."
    if error_type == "string_too_long":
        maximum_length = error_context.get("max_length")
        if maximum_length is not None:
            return f"Use no more than {maximum_length} character{'' if maximum_length == 1 else 's'}."
    return None
