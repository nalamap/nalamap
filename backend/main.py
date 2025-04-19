from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
#from sqlalchemy.ext.asyncio import AsyncSession
from services.database.database import init_db, close_db
from api import debug, geoweaver


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
    await init_db()  # Initialize DB pool when FastAPI starts
    yield
    await close_db() # close connection when app is finished
    
app = FastAPI(
    title="GeoWeaver API",
    description="API for making geospatial data accessible",
    version="0.1.0",
    lifespan=lifespan,
    openapi_tags=tags_metadata
)

# Enable CORS for all origins (adjust allow_origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify a list like ["https://example.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(debug.router)
app.include_router(geoweaver.router)

#@app.on_event("shutdown")
#async def shutdown():
#    await close_db()  # Clean up DB connections when FastAPI shuts down



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
