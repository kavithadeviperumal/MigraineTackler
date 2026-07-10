import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlmodel import Session

from app.api.routes import analyze, auth, dev, knowledge, logs, profile, shortcut
from app.config import settings
from app.database import create_db_and_tables, engine
from app.mcp_server.auth_middleware import MCPAuthMiddleware
from app.mcp_server.server import mcp

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()

    from app.graph.graph import get_graph

    threading.Thread(target=get_graph, daemon=True).start()

    def _seed_guidelines():
        from app.services.guideline_seeder import seed_guidelines

        with Session(engine) as session:
            seed_guidelines(session)

    threading.Thread(target=_seed_guidelines, daemon=True).start()
    yield


_is_prod = settings.app_env == "production"
app = FastAPI(
    title="MigraineTackler API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if _is_prod else "/docs",
    redoc_url=None if _is_prod else "/redoc",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(logs.router, prefix="/logs", tags=["logs"])
app.include_router(analyze.router, prefix="/analyze", tags=["analyze"])
app.include_router(shortcut.router, prefix="/shortcut", tags=["shortcut"])
app.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])

if settings.app_env != "production":
    app.include_router(dev.router, tags=["dev"])

app.mount("/mcp", MCPAuthMiddleware(mcp.streamable_http_app()))


@app.get("/health/ready", tags=["ops"], include_in_schema=False)
def health_ready(response: Response):
    from app.graph.graph import is_graph_ready

    if not is_graph_ready():
        response.status_code = 503
        return {"status": "not_ready", "reason": "graph compiling"}
    return {"status": "ready"}
