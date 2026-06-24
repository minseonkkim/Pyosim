"""FastAPI 진입점."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router as api_router
from app.bills import router as bills_router
from app.budget import router as budget_router
from app.config import settings
from app.health import router as health_router
from app.mismatch import router as mismatch_router
from app.persons import router as persons_router
from app.petitions import router as petitions_router
from app.watch import router as watch_router

app = FastAPI(title="표심 · Pyosim API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(persons_router)
app.include_router(bills_router)
app.include_router(budget_router)
app.include_router(petitions_router)
app.include_router(mismatch_router)
app.include_router(watch_router)
app.include_router(health_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}
