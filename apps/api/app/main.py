from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, Response

from app.api.v1.router import router as api_router
from app.core.config import get_settings
from app.core.log_redaction import configure_log_redaction

app = FastAPI(title="HealthDocs API", version="0.1.31")
settings = get_settings()
configure_log_redaction()
app.add_middleware(
	CORSMiddleware,
	allow_origins=settings.cors_origins,
	allow_credentials=True,
	allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
	allow_headers=["Content-Type"],
)
app.add_middleware(
	SessionMiddleware,
	secret_key=settings.session_secret or "development-only-session-secret",
	https_only=settings.app_env != "development",
	same_site="lax",
)


@app.middleware("http")
async def require_local_session(
	request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
	exempt_paths = {"/api/v1/health", "/api/v1/health/ai", "/api/v1/auth/login", "/docs", "/openapi.json"}
	if settings.auth_enabled and request.url.path not in exempt_paths and not request.session.get("authenticated"):
		return JSONResponse(status_code=401, content={"detail": "Authentication required."})
	return await call_next(request)


app.include_router(api_router)
