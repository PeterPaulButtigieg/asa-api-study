import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Sequence, get_args, get_origin

from fastapi import Request, Response
from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo

from app.accessibility import AccessibilityAnnotation, LinkDefinition, ValidationAnnotation
from app.dtos.common_dtos import AccessibilityDTO, AccessibilityNudgeDTO, LinkDTO
from app.errors import APIErrorItem


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
class WcagCriterion:
    number: str
    name: str
    level: Literal["A", "AA", "AAA"]
    description: str
    href: str


@dataclass(frozen=True)
class NudgeSeed:
    criterion_number: str
    type: str
    message: str
    target: str
    values: list[str] | None = None


@lru_cache(maxsize=1)
def load_wcag_index() -> dict[str, WcagCriterion]:
    with WCAG_JSON_PATH.open("r", encoding="utf-8") as wcag_file:
        wcag_payload = json.load(wcag_file)
    wcag_index: dict[str, WcagCriterion] = {}
    for principle in wcag_payload["principles"]:
        for guideline in principle["guidelines"]:
            for criterion in guideline["successcriteria"]:
                wcag_index[criterion["num"]] = WcagCriterion(
                    number=criterion["num"],
                    name=criterion["handle"],
                    level=criterion["level"],
                    description=criterion["title"],
                    href=f"{WCAG_CRITERION_BASE_URL}{criterion['id']}",
                )
    return wcag_index


def get_wcag_criterion(criterion_number: str) -> WcagCriterion:
    try:
        return load_wcag_index()[criterion_number]
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


def accessibility_requested(accessibility: bool) -> bool:
    return accessibility_available() and accessibility


def is_accessibility_enabled(request: Request) -> bool:
    raw_header_value = request.headers.get(ACCESSIBILITY_HEADER_ALIAS)
    if raw_header_value is None:
        return False
    try:
        return accessibility_requested(_BOOLEAN_ADAPTER.validate_python(raw_header_value))
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


def _normalize_values(values: Sequence[object] | None) -> list[str] | None:
    if values is None:
        return None
    normalized_values: list[str] = []
    for item in values:
        normalized_item = str(item)
        if normalized_item not in normalized_values:
            normalized_values.append(normalized_item)
    return normalized_values or None


def _extract_annotation_values(annotation: AccessibilityAnnotation, value: Any, context: Any | None) -> list[str] | None:
    if annotation.values_resolver is None:
        return None
    return _normalize_values(annotation.values_resolver(value, context))


def _extract_annotation_targets(annotation: AccessibilityAnnotation, target: str, value: Any, context: Any | None) -> list[str]:
    if annotation.targets_resolver is None:
        return [target]
    return [item for item in annotation.targets_resolver(target, value, context) or [target] if item]


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
            if not isinstance(annotation, AccessibilityAnnotation):
                continue
            values = _extract_annotation_values(annotation, value, data)
            for annotation_target in _extract_annotation_targets(annotation, target, value, data):
                seeds.append(
                    create_nudge_seed(
                        criterion_number=annotation.sc,
                        nudge_type=annotation.type.value,
                        message=annotation.message,
                        target=annotation_target,
                        values=values,
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

    grouped_nudges: dict[tuple[str, str, str], dict[str, list[str]]] = {}
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
                success_criterion=f"{criterion.number} - {criterion.name}",
                level=criterion.level,
                target=grouped["targets"],
                type=nudge_type,
                message=message,
                values=grouped["values"] or None,
                details=criterion.href,
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


def _iter_request_models(request: Request) -> list[tuple[str, type[BaseModel]]]:
    route = request.scope.get("route")
    dependant = getattr(route, "dependant", None)
    if dependant is None:
        return []
    models: list[tuple[str, type[BaseModel]]] = []
    for parameter in dependant.body_params:
        model_type = getattr(parameter, "type_", None) or getattr(getattr(parameter, "field_info", None), "annotation", None)
        if isinstance(model_type, type) and issubclass(model_type, BaseModel):
            models.append((parameter.name, model_type))
    return models


def _unwrap_model_type(annotation: Any) -> type[BaseModel] | None:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    origin = get_origin(annotation)
    if origin in {list, tuple, set, frozenset}:
        args = [argument for argument in get_args(annotation) if argument is not Ellipsis]
        return _unwrap_model_type(args[0]) if args else None
    return None


def _resolve_model_field(model_type: type[BaseModel], location_parts: Sequence[object]) -> FieldInfo | None:
    current_model: type[BaseModel] | None = model_type
    current_field: FieldInfo | None = None
    for part in location_parts:
        if isinstance(part, int):
            if current_field is None:
                return None
            current_model = _unwrap_model_type(current_field.annotation)
            continue
        if not isinstance(part, str) or current_model is None:
            return None
        current_field = current_model.model_fields.get(part)
        if current_field is None:
            return None
        current_model = _unwrap_model_type(current_field.annotation)
    return current_field


def _get_validation_annotation(request: Request, location: Sequence[object]) -> ValidationAnnotation | None:
    stripped_location = [part for part in location if not (isinstance(part, str) and part in LOCATION_PREFIXES_TO_SKIP)]
    for parameter_name, model_type in _iter_request_models(request):
        candidate_location = stripped_location[1:] if stripped_location and stripped_location[0] == parameter_name else stripped_location
        field = _resolve_model_field(model_type, candidate_location)
        if field is None:
            continue
        for metadata in field.metadata:
            if isinstance(metadata, ValidationAnnotation):
                return metadata
    return None


def get_validation_suggestion(request: Request, error: dict[str, Any]) -> str | None:
    annotation = _get_validation_annotation(request, error["loc"])
    if annotation is not None:
        if annotation.suggestion_resolver is not None:
            suggestion = annotation.suggestion_resolver(error)
            if suggestion is not None:
                return suggestion
        if annotation.suggestion is not None:
            return annotation.suggestion

    error_type = error["type"]
    error_context = error.get("ctx", {})
    if error_type == "missing":
        return "Provide a value for this field."
    if error_type == "string_too_short":
        minimum_length = error_context.get("min_length")
        if minimum_length is not None:
            return f"Use at least {minimum_length} character{'' if minimum_length == 1 else 's'}."
    if error_type == "string_too_long":
        maximum_length = error_context.get("max_length")
        if maximum_length is not None:
            return f"Use no more than {maximum_length} character{'' if maximum_length == 1 else 's'}."
    return None


def build_error_items_payload(errors: Sequence[APIErrorItem] | None) -> list[dict[str, str]]:
    payload: list[dict[str, str]] = []
    for error in errors or ():
        error_item = {"field": error.field, "message": error.message}
        if error.suggestion is not None:
            error_item["suggestion"] = error.suggestion
        payload.append(error_item)
    return payload


def build_accessibility_error_response(detail: object, errors: Sequence[APIErrorItem] | None = None) -> dict[str, object]:
    response_payload: dict[str, object] = {"detail": detail}
    error_items = build_error_items_payload(errors)
    if error_items:
        response_payload["errors"] = error_items

    nudge_seeds: list[NudgeSeed] = []
    if isinstance(detail, str):
        nudge_seeds.append(
            create_nudge_seed(
                criterion_number="4.1.3",
                nudge_type="status-message",
                message="Announce the processing or validation result as a status message without moving focus.",
                target="detail",
                values=[detail],
            )
        )

    for index, error in enumerate(error_items):
        nudge_seeds.append(
            create_nudge_seed(
                criterion_number="3.3.1",
                nudge_type="error-identification",
                message="Associate each field error message with the relevant input in error.",
                target=f"errors[{index}].message",
                values=[error["message"]],
            )
        )
        if "suggestion" in error:
            nudge_seeds.append(
                create_nudge_seed(
                    criterion_number="3.3.3",
                    nudge_type="error-suggestion",
                    message="Present the correction suggestion next to the related field error when one is available.",
                    target=f"errors[{index}].suggestion",
                    values=[error["suggestion"]],
                )
            )

    accessibility = build_accessibility_response(additional_nudge_seeds=nudge_seeds)
    if accessibility is not None:
        response_payload["accessibility"] = accessibility.model_dump()
    return response_payload
