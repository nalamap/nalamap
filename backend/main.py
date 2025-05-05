import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse


from fastapi.staticfiles import StaticFiles
#from sqlalchemy.ext.asyncio import AsyncSession
from services.database.database import init_db, close_db
from api import data_management, debug, geoweaver


tags_metadata = [
    {
        "name": "debug",
        "description": "The debug methods are used for directly interacting with the models and tools",
    },
    {
        "name": "geoweaver",
        "description": "Geoweaver API endpoints can be used to interact with the Geoweaver answer geospatial questions.",
    },
]

# File size limit (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes

# Custom middleware to check request size
class FileSizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and "/upload" in request.url.path:
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > MAX_FILE_SIZE:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "File size exceeds the 100MB limit. Please upload a smaller file."}
                )
        return await call_next(request)

app = FastAPI()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield
    await close_db()

app = FastAPI(
    title="GeoWeaver API",
    description="API for making geospatial data accessible",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata
)

# Add file size middleware
app.add_middleware(FileSizeLimitMiddleware)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Local upload directory and base URL
LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", "./uploads")
# Serve local uploads
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=LOCAL_UPLOAD_DIR), name="uploads")

app.include_router(debug.router)
app.include_router(geoweaver.router)
app.include_router(data_management.router)


# Debugging 422 errors
import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
	exc_str = f'{exc}'.replace('\n', ' ').replace('   ', ' ')
	logging.error(f"{request}: {exc_str}")
	content = {'status_code': 10422, 'message': exc_str, 'data': None}
	return JSONResponse(content=content, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

@app.exception_handler(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
async def request_entity_too_large_handler(request: Request, exc):
    return JSONResponse(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        content={"detail": "File size exceeds the 100MB limit. Please upload a smaller file."}
    )
# End debugging


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
