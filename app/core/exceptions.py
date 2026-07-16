"""
Custom exceptions and centralized error handling.
"""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")


class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class NotFoundError(AppException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status_code=404)


class ValidationError(AppException):
    def __init__(self, message: str):
        super().__init__(message, status_code=422)


class AuthenticationError(AppException):
    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, status_code=401)


class AuthorizationError(AppException):
    def __init__(self, message: str = "Permission denied"):
        super().__init__(message, status_code=403)


class FileTooLargeError(AppException):
    def __init__(self, size_mb: float, max_mb: int):
        super().__init__(
            f"File size {size_mb:.1f}MB exceeds maximum allowed {max_mb}MB",
            status_code=413,
        )


class UnsupportedFormatError(AppException):
    def __init__(self, ext: str):
        super().__init__(f"Unsupported file format: .{ext}", status_code=415)


class ProcessingError(AppException):
    def __init__(self, message: str):
        super().__init__(f"Processing failed: {message}", status_code=500)


def _is_api_request(request: Request) -> bool:
    return request.url.path.startswith("/api/")


def setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        if _is_api_request(request):
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.message, "error": type(exc).__name__},
            )
        if exc.status_code == 401:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url="/auth/login", status_code=302)
        return templates.TemplateResponse(
            request,
            "errors/error.html",
            {"status_code": exc.status_code, "message": exc.message},
            status_code=exc.status_code,
        )

    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        if _is_api_request(request):
            return JSONResponse(status_code=404, content={"detail": "Not found"})
        return templates.TemplateResponse(
            request,
            "errors/error.html",
            {"status_code": 404, "message": "الصفحة غير موجودة"},
            status_code=404,
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        if _is_api_request(request):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return templates.TemplateResponse(
            request,
            "errors/error.html",
            {"status_code": 500, "message": "خطأ داخلي في الخادم"},
            status_code=500,
        )
