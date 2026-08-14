import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_, delete
from sqlalchemy.orm import selectinload
from pydantic import BaseModel
from typing import List, Optional

from app.core.database import get_db
from app.domain.models.prospect import Prospect
from app.domain.models.contact import ProspectContact
from app.domain.models.shipment import SofttradeShipment
from app.domain.models.favorite import ProspectFavorite
from app.domain.services.geo_service import (
    check_mendoza_transit_disclaimer,
    check_camionera_mendocina_disclaimer
)

router = APIRouter(prefix="/prospects", tags=["Prospects"])

class ContactCreateSchema(BaseModel):
    name: str
    role_title: Optional[str] = "Gerente de Logística"
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    notes: Optional[str] = None

@router.get("/autocomplete-options", response_model=dict)
async def get_autocomplete_options(db: AsyncSession = Depends(get_db)):
    orig_res = await db.execute(select(SofttradeShipment.origin_str).distinct().where(SofttradeShipment.origin_str.isnot(None)))
    dest_res = await db.execute(select(SofttradeShipment.destination_str).distinct().where(SofttradeShipment.destination_str.isnot(None)))
    prod_res = await db.execute(select(SofttradeShipment.merchandise_desc).distinct().where(SofttradeShipment.merchandise_desc.isnot(None)))
    comp_res = await db.execute(select(Prospect.name).distinct().where(Prospect.name.isnot(None)))
    cat_res = await db.execute(select(Prospect.primary_category).distinct().where(Prospect.primary_category.isnot(None)))

    return {
        "origins": sorted(list(set([o.strip() for o in orig_res.scalars().all() if o and o.strip()]))),
        "destinations": sorted(list(set([d.strip() for d in dest_res.scalars().all() if d and d.strip()]))),
        "products": sorted(list(set([p.strip() for p in prod_res.scalars().all() if p and p.strip()]))),
        "companies": sorted(list(set([c.strip() for c in comp_res.scalars().all() if c and c.strip()]))),
        "categories": sorted(list(set([c.strip() for c in cat_res.scalars().all() if c and c.strip()])))
    }

@router.get("/", response_model=dict)
async def list_prospects(
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    fuente: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_trucks: int = Query(1, ge=1),
    truck_capacity_kg: float = Query(28500.0, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    query = select(Prospect)
    
    if search:
        s = f"%{search.strip()}%"
        query = query.where(or_(Prospect.name.ilike(s), Prospect.tax_id.ilike(s)))
        
    if category and category != "TODAS":
        query = query.where(Prospect.primary_category == category)
        
    if fuente and fuente in ("IMPO", "EXPO"):
        query = query.where(Prospect.fuente == fuente)
        
    if status and status != "TODOS":
        query = query.where(Prospect.status == status)
        
    if min_trucks > 1:
        query = query.where(Prospect.total_trucks >= min_trucks)
        
    query = query.order_by(Prospect.total_trucks.desc())
    
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total_count = total_result.scalar_one()
    
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await db.execute(query)
    prospects = result.scalars().all()
    
    items = []
    for p in prospects:
        items.append({
            "id": p.id,
            "name": p.name,
            "tax_id": p.tax_id,
            "fuente": p.fuente.value if hasattr(p.fuente, "value") else str(p.fuente),
            "category": p.primary_category or "Otros",
            "total_shipments": p.total_shipments,
            "total_trucks": p.total_trucks,
            "total_freight_usd": p.total_freight_usd,
            "avg_freight_per_truck_usd": p.avg_freight_per_truck_usd,
            "last_shipment_date": p.last_shipment_date.strftime("%d/%m/%Y") if p.last_shipment_date else "—",
            "status": p.status.value if hasattr(p.status, "value") else str(p.status),
        })
        
    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": (total_count + page_size - 1) // page_size,
        "items": items
    }

@router.get("/export/csv")
async def export_prospects_csv(
    db: AsyncSession = Depends(get_db)
):
    """Exporta el listado completo de prospectos calificados como archivo CSV descargable."""
    query = select(Prospect).order_by(Prospect.total_trucks.desc())
    res = await db.execute(query)
    prospects = res.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Razón Social", "RUT / CUIT", "Operación", "Categoría Principal",
        "Total Envíos", "Total Camiones", "Flete Total USD", "Promedio USD/Camión", "Último Envío"
    ])

    for p in prospects:
        writer.writerow([
            p.id,
            p.name,
            p.tax_id or "—",
            p.fuente.value if hasattr(p.fuente, "value") else str(p.fuente),
            p.primary_category or "Otros",
            p.total_shipments,
            p.total_trucks,
            f"{p.total_freight_usd:.2f}",
            f"{p.avg_freight_per_truck_usd:.2f}",
            p.last_shipment_date.strftime("%Y-%m-%d") if p.last_shipment_date else "—"
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mercotruck_leads.csv"}
    )

@router.post("/{prospect_id}/favorite")
async def toggle_prospect_favorite(
    prospect_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Agrega o remueve un cliente de la lista de Favoritos & Alertas por Email."""
    res_p = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = res_p.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    res_f = await db.execute(select(ProspectFavorite).where(
        ProspectFavorite.prospect_id == prospect_id,
        ProspectFavorite.user_id == 1
    ))
    fav = res_f.scalar_one_or_none()

    if fav:
        await db.execute(delete(ProspectFavorite).where(ProspectFavorite.id == fav.id))
        await db.commit()
        return {"status": "success", "is_favorite": False, "message": f"{prospect.name} removido de Favoritos"}
    else:
        new_fav = ProspectFavorite(prospect_id=prospect_id, user_id=1)
        db.add(new_fav)
        await db.commit()
        return {"status": "success", "is_favorite": True, "message": f"⭐ {prospect.name} guardado en Favoritos & Alertas por Email"}

@router.get("/favorites/monthly-report/csv")
async def export_favorites_monthly_csv(
    db: AsyncSession = Depends(get_db)
):
    """Genera el reporte automático de cierre de mes con los movimientos de clientes Favoritos."""
    query = select(ProspectFavorite).options(selectinload(ProspectFavorite.prospect)).where(ProspectFavorite.user_id == 1)
    res = await db.execute(query)
    favs = res.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID Empresa", "Razón Social", "RUT / CUIT", "Operación", "Categoría",
        "Camiones Mes actual", "Flete Medio USD", "Transportista Competencia Detectado", "Estado Alerta"
    ])

    for f in favs:
        p = f.prospect
        if p:
            writer.writerow([
                p.id,
                p.name,
                p.tax_id or "—",
                p.fuente.value if hasattr(p.fuente, "value") else str(p.fuente),
                p.primary_category or "Otros",
                p.total_trucks,
                f"{p.avg_freight_per_truck_usd:.2f}",
                "Softtrade Carrier Direct",
                "🟢 Monitoreado en Favoritos"
            ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mercotruck_favoritos_cierre_mes.csv"}
    )

@router.post("/favorites/monthly-report/email-sim")
async def simulate_favorites_email_alert(
    db: AsyncSession = Depends(get_db)
):
    """Simula la emisión del envío automático de email de cierre de mes a la casilla del usuario."""
    query = select(ProspectFavorite).options(selectinload(ProspectFavorite.prospect)).where(ProspectFavorite.user_id == 1)
    res = await db.execute(query)
    favs = res.scalars().all()

    count = len(favs)
    now_str = datetime.now().strftime("%B %Y")
    return {
        "status": "success",
        "sent_to": "admin@mercotruck.com",
        "monitored_clients_count": count,
        "message": f"📧 Alerta de cierre de mes enviada exitosamente con la planilla Excel de los {count} clientes favoritos monitoreados."
    }

@router.get("/{prospect_id}/contacts")
async def get_prospect_contacts(
    prospect_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene la información de contactos directos de una empresa."""
    res_p = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = res_p.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    res_c = await db.execute(select(ProspectContact).where(ProspectContact.prospect_id == prospect_id))
    contacts = res_c.scalars().all()

    return {
        "prospect_id": prospect.id,
        "name": prospect.name,
        "tax_id": prospect.tax_id or "—",
        "contacts": [
            {
                "id": c.id,
                "name": c.name,
                "role_title": c.role_title or "Gerente de Logística",
                "email": c.email or "Sin email registrado",
                "phone": c.phone or "Sin teléfono registrado",
                "linkedin_url": c.linkedin_url,
                "notes": c.notes
            }
            for c in contacts
        ]
    }

@router.post("/{prospect_id}/contacts")
async def add_prospect_contact(
    prospect_id: int,
    req: ContactCreateSchema,
    db: AsyncSession = Depends(get_db)
):
    """Agrega un nuevo contacto directo a una empresa."""
    res_p = await db.execute(select(Prospect).where(Prospect.id == prospect_id))
    prospect = res_p.scalar_one_or_none()
    if not prospect:
        raise HTTPException(status_code=404, detail="Empresa no encontrada")

    contact = ProspectContact(
        prospect_id=prospect_id,
        name=req.name,
        role_title=req.role_title,
        email=req.email,
        phone=req.phone,
        linkedin_url=req.linkedin_url,
        notes=req.notes
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)

    return {"status": "success", "contact_id": contact.id, "message": "Contacto registrado exitosamente"}

@router.get("/{prospect_id}/routes")
async def get_prospect_routes(
    prospect_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene el desglose de corredores y advertencias de aduana de una empresa en milisegundos."""
    query_routes = select(
        SofttradeShipment.origin_str,
        SofttradeShipment.destination_str,
        SofttradeShipment.border_crossing,
        SofttradeShipment.carrier_name,
        func.count(SofttradeShipment.id).label("shipment_count"),
        func.sum(SofttradeShipment.trucks_count).label("truck_count"),
        func.avg(SofttradeShipment.freight_per_truck_usd).label("avg_freight")
    ).where(
        SofttradeShipment.prospect_id == prospect_id,
        SofttradeShipment.origin_str.isnot(None)
    ).group_by(
        SofttradeShipment.origin_str,
        SofttradeShipment.destination_str,
        SofttradeShipment.border_crossing,
        SofttradeShipment.carrier_name
    ).order_by(func.sum(SofttradeShipment.trucks_count).desc()).limit(10)

    res = await db.execute(query_routes)
    routes = []
    has_mendoza = False
    has_camionera = False

    for r in res.all():
        orig = r[0] or "Origen no especifico"
        dest = r[1] or "Destino no especifico"
        border = r[2] or "LIBERTADORES"
        
        is_m = check_mendoza_transit_disclaimer(dest, "EXPO")
        is_c = check_camionera_mendocina_disclaimer(orig, dest)
        if is_m: has_mendoza = True
        if is_c: has_camionera = True

        routes.append({
            "origin": orig,
            "destination": dest,
            "border_crossing": border,
            "carrier": r[3] or "Competencia Directa",
            "shipment_count": r[4],
            "truck_count": r[5] or 1,
            "avg_freight": round(r[6] or 2500, 2),
            "is_mendoza_transit": is_m,
            "is_camionera_hub": is_c
        })

    return {
        "prospect_id": prospect_id,
        "has_mendoza_warning": has_mendoza,
        "has_camionera_warning": has_camionera,
        "routes": routes
    }
