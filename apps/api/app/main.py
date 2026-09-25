from fastapi import FastAPI

from app.api.v1.router import router as api_router

app = FastAPI(title="HealthDocs API", version="0.1.0")
app.include_router(api_router)
