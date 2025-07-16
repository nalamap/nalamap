import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api import ai_style, auto_styling, data_management, debug, nalamap, settings

# from sqlalchemy.ext.asyncio import AsyncSession
from core.config import LOCAL_UPLOAD_DIR
from services.database.database import close_db, init_db

# Configure logging to show info level messages for debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


tags_metadata = [
    {
        "name": "debug",
        "description": (
            "The debug methods are used for directly interacting with the " "models and tools"
        ),
    },
    {
        "name": "nalamap",
        "description": "NaLaMap API endpoints can be used to interact with the "
        "NaLaMap answer geospatial questions.",
    },
]

app = FastAPI()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="NaLaMap API",
    description="API for making geospatial data accessible",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata,
)

# CORS middleware - commented out to let nginx handle CORS
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# Local upload directory and base URL
# Serve local uploads
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=LOCAL_UPLOAD_DIR), name="uploads")

# Include API routers
app.include_router(debug.router, prefix="/api")
app.include_router(nalamap.router, prefix="/api")  # Main chat functionality
app.include_router(data_management.router, prefix="/api")
app.include_router(ai_style.router, prefix="/api")  # AI Style button functionality
app.include_router(auto_styling.router, prefix="/api")  # Automatic styling
app.include_router(settings.router, prefix="/api")


@app.get("/")
async def root():
    return {"message": "NaLaMap API is running"}


# Exception handlers


@app.exception_handler(status.HTTP_400_BAD_REQUEST)
async def validation_exception_handler_400(request: Request, exc):
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"{request}: {exc_str}")
    content = {"status_code": 10400, "message": exc_str, "data": None}
    return JSONResponse(content=content, status_code=status.HTTP_400_BAD_REQUEST)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler_422(request: Request, exc: RequestValidationError):
    exc_str = f"{exc}".replace("\n", " ").replace("   ", " ")
    logging.error(f"{request}: {exc_str}")
    content = {"status_code": 10422, "message": exc_str, "data": None}
    return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)


@app.exception_handler(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
async def request_entity_too_large_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={"detail": "File size exceeds the 100MB limit. Please upload a smaller file."},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
