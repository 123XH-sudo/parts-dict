from fastapi.responses import JSONResponse


def fail(status: int, detail: str) -> JSONResponse:
    return JSONResponse({"detail": detail}, status_code=status)


def csrf_from_request(request) -> str:
    return request.headers.get("X-CSRF-Token") or request.headers.get("x-csrf-token") or ""
