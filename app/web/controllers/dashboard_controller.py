import time
import json
from urllib.parse import quote
from fastapi import APIRouter, Request, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional, List, Dict, Any

from app.core.database import get_db
from app.domain.models.prospect import Prospect, ProspectStatus, ProspectFuente
from app.domain.models.shipment import SofttradeShipment
from app.domain.models.route import MercotruckRoute
from app.domain.models.tariff import MercotruckTariff
from app.domain.services.matching_engine import MatchingEngine
from app.domain.services.pricing_engine import PricingEngine
from app.domain.services.geo_service import get_coords
from app.web.jinja import templates

router = APIRouter(tags=["Web Dashboard"])

_CACHE_TTL = 300 # 5 minutes
_ROUTES_CACHE: List[Dict[str, Any]] = []
_TARIFFS_CACHE: List[Dict[str, Any]] = []
_LAST_CACHE_TIME: float = 0.0

async def get_cached_routes_and_tariffs(db: AsyncSession):
    global _ROUTES_CACHE, _TARIFFS_CACHE, _LAST_CACHE_TIME
    now = time.time()
    if not _ROUTES_CACHE or (now - _LAST_CACHE_TIME > _CACHE_TTL):
        routes_res = await db.execute(select(MercotruckRoute))
        _ROUTES_CACHE = [
            {"id": r.id, "origin": r.origin, "destination": r.destination, "border_crossing": r.border_crossing,
             "sale_price_usd": r.sale_price_usd, "cost_price_usd": r.cost_price_usd,
             "trip_date": r.trip_date, "origin_lat": r.origin_lat, "origin_lon": r.origin_lon,
             "dest_lat": r.dest_lat, "dest_lon": r.dest_lon}
            for r in routes_res.scalars().all()
        ]
        
        tariffs_res = await db.execute(select(MercotruckTariff).where(MercotruckTariff.is_active == True))
        _TARIFFS_CACHE = [
            {"id": t.id, "origin": t.origin, "destination": t.destination, "border_crossing": t.border_crossing,
             "category": t.category, "sale_price_usd": t.sale_price_usd, "estimated_carrier_cost_usd": t.estimated_carrier_cost_usd,
             "origin_lat": t.origin_lat, "origin_lon": t.origin_lon, "dest_lat": t.dest_lat, "dest_lon": t.dest_lon}
            for t in tariffs_res.scalars().all()
        ]
        _LAST_CACHE_TIME = now
    return _ROUTES_CACHE, _TARIFFS_CACHE

@router.get("/", response_class=HTMLResponse)
async def render_dashboard(
    request: Request,
    search: Optional[str] = Query(None),
    origin: Optional[str] = Query(None),
    destination: Optional[str] = Query(None),
    product: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    fuente: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    min_trucks: int = Query(1, ge=1),
    truck_capacity_kg: float = Query(28500.0, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    s_search = search if isinstance(search, str) else None
    s_origin = origin if isinstance(origin, str) else None
    s_dest = destination if isinstance(destination, str) else None
    s_prod = product if isinstance(product, str) else None
    s_cat = category if isinstance(category, str) else None
    s_fuente = fuente if isinstance(fuente, str) else None
    s_status = status if isinstance(status, str) else None
    
    try:
        i_min_trucks = int(min_trucks) if isinstance(min_trucks, (int, str)) else 1
    except (ValueError, TypeError):
        i_min_trucks = 1

    try:
        i_page = int(page) if isinstance(page, (int, str)) else 1
    except (ValueError, TypeError):
        i_page = 1

    try:
        i_page_size = int(page_size) if isinstance(page_size, (int, str)) else 10
    except (ValueError, TypeError):
        i_page_size = 10

    query = select(Prospect)

    # Buscador por Trayecto (Origen X -> Destino Y) y Producto
    if (s_origin and s_origin.strip()) or (s_dest and s_dest.strip()) or (s_prod and s_prod.strip()):
        query = query.join(SofttradeShipment, Prospect.id == SofttradeShipment.prospect_id)
        if s_origin and s_origin.strip():
            query = query.where(SofttradeShipment.origin_str.ilike(f"%{s_origin.strip()}%"))
        if s_dest and s_dest.strip():
            query = query.where(SofttradeShipment.destination_str.ilike(f"%{s_dest.strip()}%"))
        if s_prod and s_prod.strip():
            p_term = f"%{s_prod.strip()}%"
            query = query.where(or_(
                SofttradeShipment.category.ilike(p_term),
                SofttradeShipment.merchandise_desc.ilike(p_term)
            ))
        query = query.distinct()
    
    if s_search and s_search.strip():
        s = f"%{s_search.strip()}%"
        query = query.where(or_(Prospect.name.ilike(s), Prospect.tax_id.ilike(s)))
        
    if s_cat and s_cat != "TODAS":
        query = query.where(Prospect.primary_category == s_cat)
        
    if s_fuente and s_fuente in ("IMPO", "EXPO"):
        query = query.where(Prospect.fuente == s_fuente)
        
    if s_status and s_status != "TODOS":
        query = query.where(Prospect.status == s_status)
        
    if i_min_trucks > 1:
        query = query.where(Prospect.total_trucks >= i_min_trucks)
        
    # Calculate Total Count
    count_query = select(func.count()).select_from(query.subquery())
    total_count_res = await db.execute(count_query)
    total_count = total_count_res.scalar() or 0

    # Execute Paginated Query
    offset = (i_page - 1) * i_page_size
    paginated_query = query.offset(offset).limit(i_page_size)
    prospects_res = await db.execute(paginated_query)
    prospects = prospects_res.scalars().all()
    
    # Get stats for top KPI cards
    stats_query = select(
        func.count(Prospect.id),
        func.sum(Prospect.total_trucks),
        func.sum(Prospect.total_freight_usd)
    )
    stats_res = await db.execute(stats_query)
    total_prospects, total_trucks_all, total_freight_all = stats_res.one()
    
    # Get distinct categories for dropdown
    cat_query = select(Prospect.primary_category).distinct().where(Prospect.primary_category.isnot(None)).order_by(Prospect.primary_category)
    cat_res = await db.execute(cat_query)
    categories = [c for c in cat_res.scalars().all() if c]

    # Distinct Origins for Autocomplete
    orig_query = select(SofttradeShipment.origin_str).distinct().where(SofttradeShipment.origin_str.isnot(None)).order_by(SofttradeShipment.origin_str)
    orig_res = await db.execute(orig_query)
    distinct_origins = sorted(list(set([o.strip() for o in orig_res.scalars().all() if o and o.strip()])))

    # Distinct Destinations for Autocomplete
    dest_query = select(SofttradeShipment.destination_str).distinct().where(SofttradeShipment.destination_str.isnot(None)).order_by(SofttradeShipment.destination_str)
    dest_res = await db.execute(dest_query)
    distinct_destinations = sorted(list(set([d.strip() for d in dest_res.scalars().all() if d and d.strip()])))

    # Distinct Products for Autocomplete
    prod_query = select(SofttradeShipment.merchandise_desc).distinct().where(SofttradeShipment.merchandise_desc.isnot(None)).order_by(SofttradeShipment.merchandise_desc)
    prod_res = await db.execute(prod_query)
    distinct_products = sorted(list(set([p.strip() for p in prod_res.scalars().all() if p and p.strip()])))

    # Distinct Companies for Autocomplete
    comp_query = select(Prospect.name).distinct().where(Prospect.name.isnot(None)).order_by(Prospect.name)
    comp_res = await db.execute(comp_query)
    distinct_companies = sorted(list(set([c.strip() for c in comp_res.scalars().all() if c and c.strip()])))

    routes, tariffs = await get_cached_routes_and_tariffs(db)
    
    # Batch load first shipments for prospects in page
    prospect_ids = [p.id for p in prospects]
    first_shipments = {}
    if prospect_ids:
        ship_query = select(SofttradeShipment).where(SofttradeShipment.prospect_id.in_(prospect_ids))
        ship_res = await db.execute(ship_query)
        for s in ship_res.scalars().all():
            if s.prospect_id not in first_shipments:
                first_shipments[s.prospect_id] = s

    items = []
    for p in prospects:
        comp_price = p.avg_freight_per_truck_usd or 0.0
        first_ship = first_shipments.get(p.id)
        
        mercotruck_price = None
        diff_pct = None
        is_recent = False
        orig_name = "Origen no especifico"
        dest_name = "Destino no especifico"
        orig_coords = (-32.890, -68.845) # Mendoza default
        dest_coords = (-33.459, -70.648) # Santiago default
        
        if first_ship:
            orig_name = first_ship.origin_str or "Mendoza"
            dest_name = first_ship.destination_str or "Santiago"
            co = get_coords(orig_name)
            cd = get_coords(dest_name)
            if co[0]: orig_coords = co
            if cd[0]: dest_coords = cd

            match = MatchingEngine.match_shipment_to_routes_and_tariffs(
                shipment_origin_lat=co[0], shipment_origin_lon=co[1],
                shipment_dest_lat=cd[0], shipment_dest_lon=cd[1],
                shipment_border_crossing=first_ship.border_crossing or "",
                shipment_category=first_ship.category or "Otros",
                routes=routes, tariffs=tariffs
            )
            mercotruck_price = match.get("sale_price_usd")
            is_recent = match.get("is_recent_90d", False)
            if mercotruck_price and comp_price > 0:
                diff_pct = PricingEngine.calculate_price_difference_pct(mercotruck_price, comp_price)

        fuente_val = p.fuente.value if hasattr(p.fuente, "value") else str(p.fuente)
        status_val = p.status.value if hasattr(p.status, "value") else str(p.status)

        p_dict = {
            "id": p.id,
            "name": p.name,
            "tax_id": p.tax_id or "—",
            "fuente": fuente_val,
            "category": p.primary_category or "Otros",
            "total_trucks": p.total_trucks,
            "avg_freight_per_truck_usd": f"${comp_price:,.0f}",
            "mercotruck_price_usd": f"${mercotruck_price:,.0f}" if mercotruck_price else None,
            "diff_pct": diff_pct,
            "is_recent_90d": is_recent,
            "status": status_val,
            "origin_str": orig_name,
            "destination_str": dest_name,
            "origin_lat": orig_coords[0],
            "origin_lon": orig_coords[1],
            "dest_lat": dest_coords[0],
            "dest_lon": dest_coords[1],
        }
        p_dict["encoded_json"] = quote(json.dumps(p_dict))
        items.append(p_dict)
        
    tot_pages = (total_count + i_page_size - 1) // i_page_size

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "prospects": items,
            "total": total_count,
            "page": i_page,
            "page_size": i_page_size,
            "total_pages": tot_pages,
            "stats": {
                "total_prospects": total_prospects or 0,
                "total_trucks": total_trucks_all or 0,
                "total_freight_usd": f"${(total_freight_all or 0):,.0f}"
            },
            "categories": categories,
            "distinct_origins": distinct_origins,
            "distinct_destinations": distinct_destinations,
            "distinct_products": distinct_products,
            "distinct_companies": distinct_companies,
            "filters": {
                "search": s_search or "",
                "origin": s_origin or "",
                "destination": s_dest or "",
                "product": s_prod or "",
                "category": s_cat or "TODAS",
                "fuente": s_fuente or "TODAS",
                "status": s_status or "TODOS",
                "min_trucks": i_min_trucks,
                "truck_capacity_kg": 28500.0
            }
        }
    )
