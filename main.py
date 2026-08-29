import os
import time
from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.config import settings
from app.core.database import get_db
from app.domain.models.prospect import Prospect
from app.api.router import api_router
from app.web.router import web_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Middleware para prevenir el Cache agresivo de navegadores en archivos estáticos (.css / .js)
@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Mount Static Files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Service Worker dummy handler to prevent browser console 404 warnings
from fastapi.responses import Response

@app.get("/sw.js", include_in_schema=False)
async def service_worker():
    return Response(status_code=204)

# Healthcheck Endpoint
@app.get("/health", tags=["Health"])
async def health_check(db: AsyncSession = Depends(get_db)):
    """Chequeo de salud del sistema Mercotruck Enterprise y la base de datos."""
    try:
        res = await db.execute(select(func.count(Prospect.id)))
        prospects_count = res.scalar_one()
        return {
            "status": "healthy",
            "database": "connected",
            "total_qualified_prospects": prospects_count,
            "excel_files_found": {
                "HISTORICO_MERCOTRUCK": os.path.exists(os.path.join(settings.DATA_FOLDER, "HISTORICO_MERCOTRUCK.xlsx")),
                "SOFTTRADE_IMPO": os.path.exists(os.path.join(settings.DATA_FOLDER, "SOFTTRADE_IMPO.xlsx")),
                "SOFTTRADE_EXPO": os.path.exists(os.path.join(settings.DATA_FOLDER, "SOFTTRADE_EXPO.xlsx"))
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "database_error": str(e)
        }

# Include Routers
app.include_router(web_router)
app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
