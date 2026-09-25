from fastapi import FastAPI

app = FastAPI(title="HealthDocs API", version="0.1.0")


@app.get("/api/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/v1/health/ai")
def ai_health() -> dict[str, str]:
    return {"status": "not_configured"}
