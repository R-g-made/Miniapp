from fastapi import FastAPI
from backend.builders.app_builder import FastAPIBuilder
from backend.core.logger import setup_logging

# Настраиваем логирование до создания приложения
setup_logging()

def create_app() -> FastAPI:
    return (
        FastAPIBuilder()
        .with_middleware()
        .with_exception_handlers()
        .with_routers()
        .build()
    )

app = create_app()
