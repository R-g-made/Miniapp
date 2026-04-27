import asyncio
import time
import uuid
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from loguru import logger

from backend.core.config import settings
from backend.api.v1.api import api_router
from backend.core.exceptions import (
    AppError,
    app_exception_handler,
    http_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI (replaces on_event startup/shutdown)
    """

    logger.info("Starting up FastAPI application...")
    
    from backend.db.session import engine
    from backend.models.base import Base
    import backend.models
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables initialized.")

    from backend.services.worker_service import worker_service
    
    # Запускаем все фоновые воркеры (дропы, цены, разблокировки, рефаунды)
    await worker_service.start_all()
    
    yield
    
    logger.info("Shutting down FastAPI application...")

class FastAPIBuilder:
    def __init__(self):
        self._app = FastAPI(
            title=settings.PROJECT_NAME,
            lifespan=lifespan
        )

    def with_middleware(self):
        @self._app.middleware("http")
        async def logging_middleware(request: Request, call_next):
            request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
            
            with logger.contextualize(request_id=request_id):
                start_time = time.time()
                logger.info(f"REQ: {request.method} {request.url.path}")
                
                response = await call_next(request)
                
                process_time = (time.time() - start_time) * 1000
                logger.info(
                    f"RES: {request.method} {request.url.path} "
                    f"Status: {response.status_code} "
                    f"Time: {process_time:.2f}ms"
                )
                
                response.headers["X-Request-ID"] = request_id
                return response

        self._app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        return self

    def with_exception_handlers(self):
        self._app.add_exception_handler(AppError, app_exception_handler)
        self._app.add_exception_handler(StarletteHTTPException, http_exception_handler)
        self._app.add_exception_handler(RequestValidationError, validation_exception_handler)
        self._app.add_exception_handler(Exception, global_exception_handler)
        return self

    def with_routers(self):
        @self._app.get("/tonconnect-manifest.json", include_in_schema=False)
        async def get_manifest():
            path = os.path.join(os.getcwd(), "frontend", "public", "tonconnect-manifest.json")
            if os.path.exists(path):
                return FileResponse(
                    path, 
                    media_type='application/json',
                    headers={
                        "Access-Control-Allow-Origin": "*",
                        "Cache-Control": "no-cache"
                    }
                )
            return {"error": "Manifest not found"}

        self._app.include_router(api_router, prefix="/api/v1")
        return self

    def build(self) -> FastAPI:
        return self._app
