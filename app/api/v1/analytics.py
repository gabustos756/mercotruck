from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.core.database import get_db

router = APIRouter(prefix="/analytics", tags=["Analytics & Corredores"])

@router.get("/top-routes")
async def get_top_routes(
    limit: int = 15,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene las rutas comerciales más frecuentes ordenadas por camiones."""
    query = text("""
        SELECT 
            origin_str, 
            destination_str, 
            border_crossing,
            fuente,
            COUNT(*) as total_envios,
            SUM(trucks_count) as total_camiones,
            SUM(freight_usd) as flete_total_usd,
            AVG(freight_per_truck_usd) as flete_promedio_camion
        FROM softtrade_shipments
        WHERE origin_str IS NOT NULL AND destination_str IS NOT NULL
        GROUP BY origin_str, destination_str, border_crossing, fuente
        ORDER BY total_camiones DESC
        LIMIT :limit;
    """)
    
    res = await db.execute(query, {"limit": limit})
    rows = res.mappings().all()
    
    return [
        {
            "origin": r["origin_str"],
            "destination": r["destination_str"],
            "border_crossing": r["border_crossing"] or "—",
            "fuente": r["fuente"],
            "total_shipments": r["total_envios"],
            "total_trucks": r["total_camiones"],
            "total_freight_usd": float(r["flete_total_usd"] or 0),
            "avg_freight_per_truck_usd": round(float(r["flete_promedio_camion"] or 0), 2)
        }
        for r in rows
    ]
