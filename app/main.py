from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.endpoints import router


APP_DIRECTORY = Path(__file__).resolve().parent
STATIC_DIRECTORY = APP_DIRECTORY / "static"

STATIC_DIRECTORY.mkdir(
    parents=True,
    exist_ok=True,
)


origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]


app = FastAPI(
    title="Study Checkout API",
    description=(
        "Dummy product and checkout API "
        "for MSc dissertation study."
    ),
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
    ],
    allow_headers=["*"],
)


app.mount(
    "/static",
    StaticFiles(
        directory=STATIC_DIRECTORY,
    ),
    name="static",
)


app.include_router(router)


@app.get(
    "/",
    include_in_schema=False,
)
def redirect_to_docs() -> RedirectResponse:
    return RedirectResponse(
        url="/docs",
        status_code=307,
    )


@app.get(
    "/health",
    tags=["Operations"],
)
def health_check():
    return {
        "status": "healthy",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )