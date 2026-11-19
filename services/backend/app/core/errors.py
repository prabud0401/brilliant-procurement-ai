import uuid
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

DEFAULT_TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    413: "Payload Too Large",
    415: "Unsupported Media Type",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
}


class ProblemException(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        title: str | None = None,
        detail: str | None = None,
        errors: list[dict[str, Any]] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.title = title or DEFAULT_TITLES.get(status_code, "Error")
        self.detail = detail or self.title
        self.errors = errors
        self.headers = dict(headers) if headers else {}
        super().__init__(self.detail)


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or uuid.uuid4().hex


def create_problem_response(
    status_code: int,
    code: str,
    title: str,
    detail: str,
    request_id: str,
    errors: list[dict[str, Any]] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    content: dict[str, Any] = {
        "type": f"https://pda.example/errors/{code.lower().replace('_', '-')}",
        "title": title,
        "status": status_code,
        "code": code,
        "detail": detail,
        "request_id": request_id,
    }
    if errors:
        content["errors"] = errors

    res_headers = dict(headers) if headers else {}
    res_headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers=res_headers,
        media_type="application/problem+json",
    )


async def problem_exception_handler(request: Request, exc: ProblemException) -> JSONResponse:
    request_id = get_request_id(request)
    return create_problem_response(
        status_code=exc.status_code,
        code=exc.code,
        title=exc.title,
        detail=exc.detail,
        request_id=request_id,
        errors=exc.errors,
        headers=exc.headers,
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = get_request_id(request)
    code = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
    }.get(exc.status_code, "HTTP_ERROR")

    title = DEFAULT_TITLES.get(exc.status_code, "Error")
    detail = str(exc.detail) if exc.detail else title

    return create_problem_response(
        status_code=exc.status_code,
        code=code,
        title=title,
        detail=detail,
        request_id=request_id,
        headers=exc.headers,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    request_id = get_request_id(request)
    errors: list[dict[str, Any]] = []
    for err in exc.errors():
        loc = " -> ".join(str(x) for x in err.get("loc", []))
        errors.append({"field": loc, "message": err.get("msg", "Validation error")})

    return create_problem_response(
        status_code=422,
        code="VALIDATION_ERROR",
        title="Validation Error",
        detail="The request body or parameters failed validation.",
        request_id=request_id,
        errors=errors,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    return create_problem_response(
        status_code=500,
        code="INTERNAL_SERVER_ERROR",
        title="Internal Server Error",
        detail="An unexpected internal error occurred.",
        request_id=request_id,
    )
