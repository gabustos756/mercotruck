from collections import defaultdict
from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.domain.models.prospect import Prospect
from app.domain.models.shipment import SofttradeShipment
from app.domain.models.route import MercotruckRoute
from app.domain.models.tariff import MercotruckTariff
from app.domain.models.contact import ProspectContact
from app.domain.models.favorite import ProspectFavorite
from app.domain.services.matching_engine import MatchingEngine
from app.domain.services.pricing_engine import PricingEngine
from app.domain.services.geo_service import get_coords

from app.web.jinja import templates
router = APIRouter(prefix="/prospects", tags=["Web Prospect Detail"])

@router.get("/{prospect_id}", response_class=HTMLResponse)
async def render_prospect_detail(
    request: Request,
    prospect_id: int,
    db: AsyncSession = Depends(get_db)
):
    query = select(Prospect).where(Prospect.id == prospect_id)
    res = await db.execute(query)
    prospect = res.scalar_one_or_none()
    
    if not prospect:
        raise HTTPException(status_code=404, detail="Prospecto no encontrado")

    # Favorite status
    res_fav = await db.execute(select(ProspectFavorite).where(
        ProspectFavorite.prospect_id == prospect_id,
        ProspectFavorite.user_id == 1
    ))
    is_favorite = res_fav.scalar_one_or_none() is not None
        
    # Get contacts
    contacts_res = await db.execute(select(ProspectContact).where(ProspectContact.prospect_id == prospect_id))
    contacts = contacts_res.scalars().all()
    
    # Get shipments
    shipments_res = await db.execute(
        select(SofttradeShipment)
        .where(SofttradeShipment.prospect_id == prospect_id)
        .order_by(SofttradeShipment.shipment_date.desc().nullslast())
    )
    shipments = shipments_res.scalars().all()

    # Monthly Timeline Aggregation
    monthly_data = defaultdict(lambda: {"trucks": 0, "freight_sum": 0.0, "count": 0})
    for s in shipments:
        if s.shipment_date:
            key = s.shipment_date.strftime("%Y-%m")
            monthly_data[key]["trucks"] += (s.trucks_count or 1)
            monthly_data[key]["freight_sum"] += (s.freight_per_truck_usd or 0.0)
            monthly_data[key]["count"] += 1

    sorted_months = sorted(monthly_data.keys())
    max_trucks = max([m["trucks"] for m in monthly_data.values()], default=1)

    monthly_timeline = []
    for m in sorted_months[-12:]: # Last 12 months
        dt = datetime.strptime(m, "%Y-%m")
        t_count = monthly_data[m]["trucks"]
        c_count = monthly_data[m]["count"]
        avg_f = round(monthly_data[m]["freight_sum"] / c_count, 2) if c_count > 0 else 0.0
        h_pct = min(100, max(15, int((t_count / max_trucks) * 100)))

        monthly_timeline.append({
            "month_key": m,
            "month_label": dt.strftime("%b %Y"),
            "trucks": t_count,
            "avg_freight": f"${avg_f:,.0f}",
            "height_pct": h_pct
        })
    
    # Get Mercotruck historical routes
    routes_res = await db.execute(select(MercotruckRoute))
    routes = [
        {
            "id": r.id,
            "origin": r.origin,
            "destination": r.destination,
            "border_crossing": r.border_crossing,
            "sale_price_usd": r.sale_price_usd,
            "cost_price_usd": r.cost_price_usd,
            "origin_lat": r.origin_lat,
            "origin_lon": r.origin_lon,
            "dest_lat": r.dest_lat,
            "dest_lon": r.dest_lon
        }
        for r in routes_res.scalars().all()
    ]

    # Get Mercotruck Master Tariffs
    tariffs_res = await db.execute(select(MercotruckTariff).where(MercotruckTariff.is_active == True))
    tariffs = [
        {
            "id": t.id,
            "origin": t.origin,
            "destination": t.destination,
            "border_crossing": t.border_crossing,
            "category": t.category,
            "sale_price_usd": t.sale_price_usd,
            "estimated_carrier_cost_usd": t.estimated_carrier_cost_usd,
            "origin_lat": t.origin_lat,
            "origin_lon": t.origin_lon,
            "dest_lat": t.dest_lat,
            "dest_lon": t.dest_lon
        }
        for t in tariffs_res.scalars().all()
    ]
    
    shipment_list = []
    for s in shipments:
        co = get_coords(s.origin_str)
        cd = get_coords(s.destination_str)
        
        match = MatchingEngine.match_shipment_to_routes_and_tariffs(
            shipment_origin_lat=co[0],
            shipment_origin_lon=co[1],
            shipment_dest_lat=cd[0],
            shipment_dest_lon=cd[1],
            shipment_border_crossing=s.border_crossing or "",
            shipment_category=s.category or "Otros",
            routes=routes,
            tariffs=tariffs
        )
        
        sale_price = match.get("sale_price_usd")
        diff_pct = None
        if sale_price and s.freight_per_truck_usd > 0:
            diff_pct = PricingEngine.calculate_price_difference_pct(sale_price, s.freight_per_truck_usd)
            
        shipment_list.append({
            "id": s.id,
            "date": s.shipment_date.strftime("%d/%m/%Y") if s.shipment_date else "—",
            "doc_id": s.doc_id,
            "origin": s.origin_str,
            "destination": s.destination_str,
            "border_crossing": s.border_crossing,
            "carrier_name": s.carrier_name or "Desconocido",
            "weight_kg": f"{s.weight_kg:,.0f}" if s.weight_kg else "—",
            "trucks_count": s.trucks_count,
            "freight_per_truck_usd": f"${s.freight_per_truck_usd:,.0f}" if s.freight_per_truck_usd else "—",
            "mercotruck_price_usd": f"${sale_price:,.0f}" if sale_price else "Sin tarifa",
            "diff_pct": diff_pct,
            "match_source": match.get("source"),
            "is_recent_90d": match.get("is_recent_90d", False)
        })
        
    return templates.TemplateResponse("prospect_detail.html", {
        "request": request,
        "prospect": prospect,
        "contacts": contacts,
        "shipments": shipment_list,
        "monthly_timeline": monthly_timeline,
        "is_favorite": is_favorite
    })
