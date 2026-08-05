import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

from fastapi import Request, Response
from pydantic import TypeAdapter, ValidationError

from app.dtos.common_dtos import AccessibilityDTO


ACCESSIBILITY_HEADER_ALIAS = "Accessibility"
ACCESSIBILITY_HEADER_DESCRIPTION = "Set to true to include relevant WCAG 2.2 accessibility guidance."
WCAG_CRITERION_BASE_URL = "https://www.w3.org/TR/WCAG22/#"
WCAG_JSON_PATH = Path(__file__).resolve().parent.parent / "static" / "wcag.json"
LOCATION_PREFIXES_TO_SKIP = {"body", "query", "path", "header", "cookie"}
_BOOLEAN_ADAPTER = TypeAdapter(bool)

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

def build_accessibility_dto(criterion_number: str, applies_to: Sequence[str]) -> AccessibilityDTO:
    criterion = get_wcag_criterion(criterion_number)
    return AccessibilityDTO(
        sc=f"{criterion['num']} - {criterion['handle']}",
        content=criterion["title"],
        level=criterion["level"],
        href=f"{WCAG_CRITERION_BASE_URL}{criterion['id']}",
        applies_to=list(applies_to),
    )

def build_accessibility_dtos(mappings: Sequence[tuple[str, str]]) -> list[AccessibilityDTO]:
    grouped_mappings: dict[str, list[str]] = {}
    for criterion_number, applies_to in mappings:
        grouped_mappings.setdefault(criterion_number, [])
        if applies_to not in grouped_mappings[criterion_number]:
            grouped_mappings[criterion_number].append(applies_to)
    return [build_accessibility_dto(criterion_number, applies_to) for criterion_number, applies_to in grouped_mappings.items()]

def append_accessibility_vary_header(response: Response) -> None:
    existing_vary = response.headers.get("Vary")
    if existing_vary is None:
        response.headers["Vary"] = ACCESSIBILITY_HEADER_ALIAS
        return
    vary_values = [vary_value.strip() for vary_value in existing_vary.split(",") if vary_value.strip()]
    if ACCESSIBILITY_HEADER_ALIAS.lower() not in {vary_value.lower() for vary_value in vary_values}:
        vary_values.append(ACCESSIBILITY_HEADER_ALIAS)
    response.headers["Vary"] = ", ".join(vary_values)

def is_accessibility_enabled(request: Request) -> bool:
    raw_header_value = request.headers.get(ACCESSIBILITY_HEADER_ALIAS)
    if raw_header_value is None:
        return False
    try:
        return _BOOLEAN_ADAPTER.validate_python(raw_header_value)
    except ValidationError:
        return False

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
        "quantity": (
            "Enter a whole number within the allowed range."
        ),
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
