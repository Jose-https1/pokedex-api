from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.openapi.utils import get_openapi

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.limiter import limiter
from app.logging_config import logger

from .config import settings
from .database import create_db_and_tables
from .routers import (
    auth as auth_router,
    pokemon as pokemon_router,
    pokedex as pokedex_router,
    teams as teams_router,
)

from fastapi.middleware.cors import CORSMiddleware

# Crear la app FastAPI usando los ajustes de config
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

# ---------- CORS ----------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # React dev
        "http://localhost:5173",   # Vite dev
        "https://tu-dominio.com",  # Producción (placeholder)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=3600,
)

# ---------- SlowAPI (rate limiting) ----------

# Guardar el limiter en el estado de la app
app.state.limiter = limiter

# Middleware que aplica el rate limiting
app.add_middleware(SlowAPIMiddleware)


# Handler personalizado para rate limit excedido (log + handler por defecto) (lo hacemos síncrono)
@app.exception_handler(RateLimitExceeded)
def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    logger.warning(
        "Rate limit exceeded: %s %s | detail=%s",
        request.method,
        request.url.path,
        exc.detail,
    )
    return _rate_limit_exceeded_handler(request, exc)


# (No hace falta app.add_exception_handler de nuevo, el decorador ya lo registra)


# ---------- Middleware de logging de peticiones ----------

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.utcnow()

    logger.info("Request: %s %s", request.method, request.url.path)

    response = await call_next(request)

    duration = (datetime.utcnow() - start_time).total_seconds()
    logger.info(
        "Response: %s %s | status=%d | duration=%.3fs",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response


# ---------- OpenAPI personalizado con botón "Authorize" ----------

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.app_name,
        version=settings.app_version,
        description="API REST para la práctica",
        routes=app.routes,
    )

    # Definimos el esquema de seguridad tipo Bearer JWT
    openapi_schema.setdefault("components", {})
    openapi_schema["components"].setdefault("securitySchemes", {})
    openapi_schema["components"]["securitySchemes"]["BearerAuth"] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
    }

    # Añadimos el requisito de seguridad por defecto a todas las operaciones
    for path in openapi_schema["paths"].values():
        for operation in path.values():
            operation.setdefault("security", [{"BearerAuth": []}])

    app.openapi_schema = openapi_schema
    return openapi_schema


app.openapi = custom_openapi


# ---------- Eventos ----------

@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()
    logger.info("Application startup completed")


# ---------- Routers ----------

app.include_router(auth_router.router)
app.include_router(pokemon_router.router)
app.include_router(pokedex_router.router)

app.include_router(pokedex_router.router_v2)
app.include_router(teams_router.router)


# Endpoint simple de healthcheck (sin autenticación)
@app.get("/health")
def health_check():
    return {"status": "ok"}
