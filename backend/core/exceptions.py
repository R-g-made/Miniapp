from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import Any, Dict, Optional

class AppError(Exception):
    """Base class for application exceptions."""
    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(message)

class EntityNotFound(AppError):
    def __init__(self, message: str = "Entity not found"):
        super().__init__(
            message=message,
            code="ENTITY_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND
        )

class InvalidOperation(AppError):
    def __init__(self, message: str = "Invalid operation"):
        super().__init__(
            message=message,
            code="INVALID_OPERATION",
            status_code=status.HTTP_400_BAD_REQUEST
        )

class InsufficientFunds(AppError):
    def __init__(self, currency: str):
        super().__init__(
            message=f"Insufficient funds in {currency}",
            code="INSUFFICIENT_FUNDS",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={"currency": currency}
        )

class InvalidToken(AppError):
    def __init__(self, message: str = "Invalid token"):
        super().__init__(
            message=message,
            code="INVALID_TOKEN",
            status_code=status.HTTP_401_UNAUTHORIZED
        )

async def app_exception_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": exc.code,
            "message": exc.message,
            "details": exc.details
        }
    )

async def global_exception_handler(request: Request, exc: Exception):
    from backend.core.config import settings
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "code": "INTERNAL_ERROR",
            "message": "Internal server error",
            "details": str(exc) if settings.DEBUG else None
        }
    )

async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "code": "HTTP_ERROR",
            "message": str(exc.detail),
        }
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "code": "VALIDATION_ERROR",
            "message": "Validation error",
            "details": exc.errors()
        }
    )