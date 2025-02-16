from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from services.ai_service import generate_ai_response

app = FastAPI(
    title="GeoWeaver API",
    description="API for making geospatial data accessible",
    version="0.1.0"
)

class AIRequest(BaseModel):
    message: str
    # TODO: Add additional information, like map data and layers in json

class AIResponse(BaseModel):
    response: str

@app.post("/api/geoweaver/generate", 
        response_model=AIResponse,
    summary="Generate GeoWeaver Response",
    description="Receives a message and returns an AI-generated response using GeoWeaverAI.",
    tags=["GeoWeaver"])
async def get_ai_response(request: AIRequest):
    try:
        result = generate_ai_response(request.message)
        return AIResponse(response=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
