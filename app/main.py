from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.limiter import limiter

from .config import settings
from .database import create_db_and_tables
from .routers import (
    auth as auth_router,
    pokemon as pokemon_router,
    pokedex as pokedex_router,
    teams as teams_router,
)


# Crear la app FastAPI usando los ajustes de config
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

# ---------- Integración SlowAPI (rate limiting) ----------

# Guardar el limiter en el estado de la app
app.state.limiter = limiter

# Middleware que aplica el rate limiting
app.add_middleware(SlowAPIMiddleware)

# Manejador de excepción cuando se excede el límite
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


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


# ---------- Routers ----------

app.include_router(auth_router.router)
app.include_router(pokemon_router.router)
app.include_router(pokedex_router.router)
app.include_router(teams_router.router)


# Endpoint simple de healthcheck (sin autenticación)
@app.get("/health")
def health_check():
    return {"status": "ok"}
