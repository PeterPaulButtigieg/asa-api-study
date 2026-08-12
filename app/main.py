from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.endpoints import router
from app.errors import APIErrorItem, APIException
from app.services.accessibility_service import (
    append_accessibility_vary_header,
    build_accessibility_error_response,
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
    yield


app = FastAPI(
    title="Study Checkout API",
    description="Dummy product, cart, and checkout API for MSc dissertation study.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory=STATIC_DIRECTORY), name="static")
app.include_router(router)


@app.exception_handler(StarletteHTTPException)
async def accessibility_http_exception_handler(request: Request, exc: StarletteHTTPException):
    if not is_accessibility_enabled(request):
        response = await http_exception_handler(request, exc)
        append_accessibility_vary_header(response)
        return response

    errors = exc.errors if isinstance(exc, APIException) else ()
    response = JSONResponse(
        status_code=exc.status_code,
        content=build_accessibility_error_response(exc.detail, errors=errors),
        headers=exc.headers,
    )
    append_accessibility_vary_header(response)
    return response


@app.exception_handler(RequestValidationError)
async def accessibility_validation_exception_handler(request: Request, exc: RequestValidationError):
    if not is_accessibility_enabled(request):
        response = await request_validation_exception_handler(request, exc)
        append_accessibility_vary_header(response)
        return response

    validation_errors = []
    for error in exc.errors():
        validation_errors.append(
            APIErrorItem(
                field=to_readable_error_field(error["loc"]) or "request",
                message=error["msg"],
                suggestion=get_validation_suggestion(request, error),
            )
        )

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
