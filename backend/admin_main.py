from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.v1.endpoints.admin import router as admin_router
from backend.core.config import settings
from backend.core.logger import setup_logging

setup_logging()

def create_admin_app() -> FastAPI:
    app = FastAPI(title=f"{settings.PROJECT_NAME} Admin API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"], # Для админки можно разрешить все или указать конкретные
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app

app = create_admin_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
