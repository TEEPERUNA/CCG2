from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.db import SessionLocal
from app.routers import agreements, customers, guides, laptops, tickets
from app.schemas import Health

app = FastAPI(
    title="Company Brain API",
    version="0.1.0",
    description="Internal API for Ember Island IT Services support technicians.",
)

for r in (customers, laptops, tickets, agreements, guides):
    app.include_router(r.router)


@app.get("/api/health", response_model=Health, tags=["health"])
def health():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        return Health(status="ok", database="ok")
    except Exception:
        return JSONResponse(status_code=503, content={"status": "degraded", "database": "down"})
