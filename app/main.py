import time
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.exceptions import register_exception_handlers
from app.core.logging import logger, request_id_ctx_var, setup_logging
from app.core.redis import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and graceful shutdown lifecycle."""
    # --- Startup ---
    setup_logging()
    logger.info(
        f"Starting {settings.APP_NAME} v{settings.APP_VERSION} [{settings.ENVIRONMENT}]..."
    )
    await init_db()
    await init_redis()
    logger.info("Application startup completed successfully.")

    yield

    # --- Shutdown ---
    logger.info("Shutting down application...")
    await close_redis()
    await close_db()
    logger.info("Application shutdown complete.")


def create_application() -> FastAPI:
    """Application factory for FastAPI service."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        docs_url="/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        redoc_url="/redoc" if settings.DEBUG or settings.ENVIRONMENT != "production" else None,
        lifespan=lifespan,
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Request Correlation ID & Access Logging Middleware
    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next) -> Response:
        # Extract or generate Request ID
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_ctx_var.set(request_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = request_id

            logger.info(
                f"{request.method} {request.url.path} "
                f"status={response.status_code} duration={duration_ms}ms"
            )
            return response
        except Exception as exc:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.error(
                f"{request.method} {request.url.path} failed: {exc} "
                f"duration={duration_ms}ms"
            )
            raise
        finally:
            request_id_ctx_var.reset(token)

    # 3. Exception Handlers
    register_exception_handlers(app)

    # 4. API Routers
    # Mounted under API_V1_PREFIX (/api/v1) and directly at root for specification compliance
    from app.api.v1.endpoints import drivers, rides
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)
    app.include_router(rides.router, prefix="/rides", tags=["Rides (Root)"], include_in_schema=False)
    app.include_router(drivers.router, prefix="/drivers", tags=["Drivers (Root)"], include_in_schema=False)

    # 5. Root endpoint
    @app.get("/", include_in_schema=False)
    async def root() -> JSONResponse:
        return JSONResponse(
            content={
                "name": settings.APP_NAME,
                "version": settings.APP_VERSION,
                "environment": settings.ENVIRONMENT,
                "docs": "/docs" if settings.DEBUG or settings.ENVIRONMENT != "production" else "disabled in production",
                "health": f"{settings.API_V1_PREFIX}/health",
            }
        )

    return app


app = create_application()

