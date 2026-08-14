from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from typing import List

from app.core.database import get_db
from app.domain.models.tariff import MercotruckTariff
from app.domain.schemas.tariff import TariffCreate, TariffUpdate, TariffResponse
from app.domain.services.geo_service import get_coords

router = APIRouter(prefix="/tariffs", tags=["Tariffs ABM"])

@router.get("/", response_model=List[TariffResponse])
async def list_tariffs(
    db: AsyncSession = Depends(get_db)
):
    """Obtiene el listado completo de tarifas propias de Mercotruck."""
    query = select(MercotruckTariff).order_by(MercotruckTariff.updated_at.desc())
    res = await db.execute(query)
    return res.scalars().all()

@router.post("/", response_model=TariffResponse)
async def create_tariff(
    req: TariffCreate,
    db: AsyncSession = Depends(get_db)
):
    """Crea una nueva tarifa propia en el Tarifario Maestro."""
    co = get_coords(req.origin)
    cd = get_coords(req.destination)
    
    tariff = MercotruckTariff(
        origin=req.origin,
        destination=req.destination,
        border_crossing=req.border_crossing,
        category=req.category or "Todas",
        truck_type=req.truck_type or "General",
        sale_price_usd=req.sale_price_usd,
        estimated_carrier_cost_usd=req.estimated_carrier_cost_usd,
        is_active=req.is_active,
        origin_lat=co[0],
        origin_lon=co[1],
        dest_lat=cd[0],
        dest_lon=cd[1]
    )
    
    db.add(tariff)
    await db.commit()
    await db.refresh(tariff)
    return tariff

@router.put("/{tariff_id}", response_model=TariffResponse)
async def update_tariff(
    tariff_id: int,
    req: TariffUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Actualiza una tarifa propia existente."""
    query = select(MercotruckTariff).where(MercotruckTariff.id == tariff_id)
    res = await db.execute(query)
    tariff = res.scalar_one_or_none()
    
    if not tariff:
        raise HTTPException(status_code=404, detail="Tarifa no encontrada")
        
    data = req.dict(exclude_unset=True)
    for key, val in data.items():
        setattr(tariff, key, val)
        
    if "origin" in data or "destination" in data:
        co = get_coords(tariff.origin)
        cd = get_coords(tariff.destination)
        tariff.origin_lat = co[0]
        tariff.origin_lon = co[1]
        tariff.dest_lat = cd[0]
        tariff.dest_lon = cd[1]
        
    await db.commit()
    await db.refresh(tariff)
    return tariff

@router.delete("/{tariff_id}", response_model=dict)
async def delete_tariff(
    tariff_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Elimina una tarifa propia."""
    query = select(MercotruckTariff).where(MercotruckTariff.id == tariff_id)
    res = await db.execute(query)
    tariff = res.scalar_one_or_none()
    
    if not tariff:
        raise HTTPException(status_code=404, detail="Tarifa no encontrada")
        
    await db.delete(tariff)
    await db.commit()
    return {"status": "success", "message": "Tarifa eliminada correctamente"}
