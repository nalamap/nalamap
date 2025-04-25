import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


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

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local upload directory and base URL
LOCAL_UPLOAD_DIR = os.getenv("LOCAL_UPLOAD_DIR", "./uploads")
# Serve local uploads
os.makedirs(LOCAL_UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=LOCAL_UPLOAD_DIR), name="uploads")

app.include_router(debug.router)
app.include_router(geoweaver.router)
app.include_router(data_management.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
