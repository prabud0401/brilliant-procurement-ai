import time
import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.approvals.router import router as approvals_router
from app.audit.router import router as audit_router
from app.audit.service import record as record_audit
from app.comparison.router import router as comparisons_router
from app.core.config import settings
from app.core.database import engine, get_db
from app.core.errors import (
    ProblemException,
    http_exception_handler,
    problem_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.middleware import RequestIdMiddleware
from app.core.models import User
from app.core.policy import Principal, get_current_principal
from app.core.security import create_access_token, verify_password
from app.matching.router import exceptions_router, matches_router
from app.orders.router import po_router, pr_router
from app.settings_api.router import router as settings_router

# Simple in-memory IP rate limiter for login
LOGIN_ATTEMPTS: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60.0  # seconds
MAX_ATTEMPTS = 10


def check_login_rate_limit(client_ip: str) -> None:
    now = time.time()
    history = [t for t in LOGIN_ATTEMPTS[client_ip] if now - t < RATE_LIMIT_WINDOW]
    if len(history) >= MAX_ATTEMPTS:
        raise ProblemException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            code="RATE_LIMIT_EXCEEDED",
            title="Too Many Requests",
            detail="Too many failed login attempts. Please try again later.",
        )
    LOGIN_ATTEMPTS[client_ip] = history


def record_login_attempt(client_ip: str) -> None:
    LOGIN_ATTEMPTS[client_ip].append(time.time())


app = FastAPI(
    title="Procurement Document Assistant API",
    version="1.0.0",
    docs_url="/api/docs" if settings.APP_ENV in ("local", "dev") else None,
    openapi_url="/api/v1/openapi.json",
)

# Middleware
app.add_middleware(RequestIdMiddleware)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Exception handlers per Design 5.2
app.add_exception_handler(ProblemException, problem_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(Exception, unhandled_exception_handler)


# Health routes
@app.get("/healthz", tags=["health"])
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz", tags=["health"])
def readyz() -> dict[str, str]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception as exc:
        raise ProblemException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="DATABASE_UNAVAILABLE",
            title="Service Unavailable",
            detail=f"Database readiness check failed: {exc}",
        )


# Auth models
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MeResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    roles: list[str]
    department_id: uuid.UUID | None
    department_name: str | None
    approval_limit_aed: Decimal
    is_demo: bool
    active: bool


# Auth router
auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/login", response_model=TokenResponse)
def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    client_ip = request.client.host if request.client else "127.0.0.1"
    check_login_rate_limit(client_ip)

    user = db.query(User).filter(User.email == req.email.lower()).first()
    if (
        not user
        or not user.active
        or not user.password_hash
        or not verify_password(req.password, user.password_hash)
    ):
        record_login_attempt(client_ip)
        record_audit(
            session=db,
            actor=None,
            action="auth.login_failed",
            entity_type="auth",
            entity_id=user.id if user else None,
            reason=f"Failed login attempt for email {req.email}",
            after={"email": req.email.lower()},
        )
        db.commit()
        raise ProblemException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="INVALID_CREDENTIALS",
            title="Unauthorized",
            detail="Invalid email or password",
        )

    roles = [r.role for r in user.roles]
    token, expires_in = create_access_token(
        user_id=user.id,
        email=user.email,
        roles=roles,
        department_id=user.department_id,
        approval_limit_aed=user.approval_limit_aed,
    )

    record_audit(
        session=db,
        actor=user,
        action="auth.login_success",
        entity_type="user",
        entity_id=user.id,
        reason="Password login successful",
    )
    db.commit()

    return TokenResponse(access_token=token, expires_in=expires_in)


# Main API router /api/v1
api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(auth_router)
api_v1.include_router(audit_router)
api_v1.include_router(pr_router)
api_v1.include_router(po_router)
api_v1.include_router(approvals_router)
api_v1.include_router(comparisons_router)
api_v1.include_router(matches_router)
api_v1.include_router(exceptions_router)
api_v1.include_router(settings_router)


@api_v1.get("/me", response_model=MeResponse, tags=["auth"])
def get_me(principal: Principal = Depends(get_current_principal)) -> MeResponse:
    return MeResponse(
        id=principal.id,
        email=principal.email,
        display_name=principal.display_name,
        roles=principal.roles,
        department_id=principal.department_id,
        department_name=principal.department_name,
        approval_limit_aed=principal.approval_limit_aed,
        is_demo=principal.is_demo,
        active=principal.active,
    )


app.include_router(api_v1)
