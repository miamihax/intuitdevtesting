import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .import_watcher import start_watcher
from .routers import agent, drivers, imports, office, quickbooks, routes

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # On serverless platforms (e.g. Vercel) a background filesystem watcher
    # may not be able to start at all — that must not take the whole API down.
    try:
        observer = start_watcher()
    except OSError:
        observer = None
    yield
    if observer is not None:
        observer.stop()
        observer.join()


app = FastAPI(title="OptiRoute API", lifespan=lifespan)

frontend_origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[frontend_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(agent.router)
app.include_router(imports.router)
app.include_router(quickbooks.router)
app.include_router(office.router)
app.include_router(drivers.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
