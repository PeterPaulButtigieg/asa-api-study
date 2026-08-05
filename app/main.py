from contextlib import asynccontextmanager
from pathlib import Path

from annotated_types import Le
from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.data import PRODUCTS
from app.dtos.order_dtos import OrderInDTO
from app.endpoints import router
from app.services.accessibility_service import (
    append_accessibility_vary_header,
    build_accessibility_dtos,
    get_validation_suggestion,
    is_accessibility_enabled,
    to_readable_error_field,
)


APP_DIRECTORY = Path(__file__).resolve().parent
STATIC_DIRECTORY = APP_DIRECTORY / "static"
STATIC_DIRECTORY.mkdir(parents=True, exist_ok=True)
origins = ["http://localhost:5173", "http://127.0.0.1:5173"]


@asynccontextmanager
async def lifespan(_: FastAPI):
    print("TINSIEX TBIDDEL ORIGINS TO PARTICIPANTS NETWORK")
    yield


app = FastAPI(
    title="Study Checkout API",
    description="Dummy product and checkout API for MSc dissertation study.",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")
app.include_router(router)


def get_quantity_upper_bound() -> int | None:
    quantity_field = OrderInDTO.model_fields["quantity"]
    for metadata in quantity_field.metadata:
        if isinstance(metadata, Le):
            return metadata.le
    return None


def build_quantity_unavailable_suggestion(
    product_id: int | None,
) -> str:
    quantity_upper_bound = get_quantity_upper_bound()
    if product_id is None:
        if quantity_upper_bound is None:
            return "Enter a valid quantity."
        return f"Enter a quantity between 1 and {quantity_upper_bound}."
    product = PRODUCTS.get(product_id)
    if product is None:
        return "Use a product ID returned by GET /api/v1/products."
    available_quantity = product["available_quantity"]
    if quantity_upper_bound is None:
        maximum_quantity = available_quantity
    else:
        maximum_quantity = min(available_quantity, quantity_upper_bound)
    if maximum_quantity < 1:
        return "This product is currently unavailable."
    return f"Enter a quantity between 1 and {maximum_quantity}."


def build_http_error_items(
    request: Request,
    detail: str,
) -> list[dict[str, str]]:
    if request.method == "POST" and request.url.path == "/api/v1/orders":
        if detail == "Product not found":
            return [
                {
                    "field": "product_id",
                    "message": detail,
                    "suggestion": "Use a product ID returned by GET /api/v1/products.",
                }
            ]
        if detail == "Requested quantity is unavailable":
            order_context = getattr(request.state, "order_context", {})
            return [
                {
                    "field": "quantity",
                    "message": detail,
                    "suggestion": build_quantity_unavailable_suggestion(order_context.get("product_id")),
                }
            ]
        if detail == "Payment failed":
            return [
                {
                    "field": "payment.card_number",
                    "message": detail,
                    "suggestion": "Use the successful test card number 4242 4242 4242 4242.",
                }
            ]
    return []


def build_accessibility_error_response(
    detail: object,
    errors: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    response_payload: dict[str, object] = {"detail": detail}
    if errors:
        response_payload["errors"] = errors
    accessibility_mappings: list[tuple[str, str]] = []
    if isinstance(detail, str):
        accessibility_mappings.append(("4.1.3", "detail"))
    for index, error in enumerate(errors or []):
        accessibility_mappings.append(("3.3.1", f"errors[{index}].message"))
        if error.get("suggestion"):
            accessibility_mappings.append(("3.3.3", f"errors[{index}].suggestion"))
    accessibility = build_accessibility_dtos(accessibility_mappings)
    if accessibility:
        response_payload["accessibility"] = [item.model_dump() for item in accessibility]
    return response_payload


@app.exception_handler(StarletteHTTPException)
async def accessibility_http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
):
    if not is_accessibility_enabled(request):
        response = await http_exception_handler(request, exc)
        append_accessibility_vary_header(response)
        return response
    detail = exc.detail
    errors = []
    if isinstance(detail, str):
        errors = build_http_error_items(request, detail)
    response = JSONResponse(
        status_code=exc.status_code,
        content=build_accessibility_error_response(detail, errors=errors or None),
        headers=exc.headers,
    )
    append_accessibility_vary_header(response)
    return response


@app.exception_handler(RequestValidationError)
async def accessibility_validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    if not is_accessibility_enabled(request):
        response = await request_validation_exception_handler(request, exc)
        append_accessibility_vary_header(response)
        return response
    validation_errors = []
    for error in exc.errors():
        field = to_readable_error_field(error["loc"]) or "request"
        validation_error = {"field": field, "message": error["msg"]}
        suggestion = get_validation_suggestion(field, error)
        if suggestion is not None:
            validation_error["suggestion"] = suggestion
        validation_errors.append(validation_error)
    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=build_accessibility_error_response("Request validation failed", errors=validation_errors),
    )
    append_accessibility_vary_header(response)
    return response


@app.get("/", include_in_schema=False)
def redirect_to_docs() -> RedirectResponse:
    return RedirectResponse(url="/docs", status_code=307)


@app.get("/health", tags=["Operations"])
def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
