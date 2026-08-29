import time
import json
from datetime import date, datetime
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

_EVALUATED_PROSPECTS_CACHE: List[Dict[str, Any]] = []
_LAST_EVAL_CACHE_TIME: float = 0.0

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

async def get_all_evaluated_prospects_cache(db: AsyncSession, force_reload: bool = False):
    global _EVALUATED_PROSPECTS_CACHE, _LAST_EVAL_CACHE_TIME
    now = time.time()
    if not _EVALUATED_PROSPECTS_CACHE or force_reload or (now - _LAST_EVAL_CACHE_TIME > _CACHE_TTL):
        routes, tariffs = await get_cached_routes_and_tariffs(db)
        
        # Query all prospects
        prospects_res = await db.execute(select(Prospect).order_by(Prospect.total_trucks.desc()))
        prospects = prospects_res.scalars().all()
        
        # Query all shipments ordered by date
        ship_res = await db.execute(select(SofttradeShipment).order_by(SofttradeShipment.shipment_date.desc()))
        all_shipments = ship_res.scalars().all()
        
        prospect_shipments = {}
        for s in all_shipments:
            if s.prospect_id not in prospect_shipments:
                prospect_shipments[s.prospect_id] = []
            prospect_shipments[s.prospect_id].append(s)

        items = []
        today = date.today()

        for p in prospects:
            comp_price = p.avg_freight_per_truck_usd or 0.0
            ships = prospect_shipments.get(p.id, [])
            first_ship = ships[0] if ships else None

            orig_name = "ROSARIO"
            dest_name = "SANTIAGO"
            paso_name = "LIBERTADORES"
            carrier_name = "Trans Competidor SRL"
            mercaderias_set = set()
            orig_coords = (-32.890, -68.845)
            dest_coords = (-33.459, -70.648)

            docs_list = []
            calc_cards = []
            last_date = p.last_shipment_date

            for s in ships:
                if s.merchandise_desc:
                    mercaderias_set.add(s.merchandise_desc.strip().upper())
                if s.category:
                    mercaderias_set.add(s.category.strip().upper())
                if s.carrier_name and s.carrier_name.strip():
                    carrier_name = s.carrier_name.strip()
                if s.border_crossing and s.border_crossing.strip():
                    paso_name = s.border_crossing.strip()
                if s.shipment_date and (not last_date or s.shipment_date > last_date):
                    last_date = s.shipment_date

                kg = s.gross_weight_kg or 0.0
                bultos = 0
                cam = s.trucks_count or 1
                flete = s.freight_usd or 0.0

                kpp = kg / bultos if bultos > 0 else 0
                if bultos == 0:
                    tag = "GRANEL"
                    log = f"{kg:,.0f} kg ÷ 28.500 = <span class='cr'>{cam} cam</span>"
                elif kpp < 50:
                    tag = f"BULTOS LIGEROS ({kpp:.0f} kg/bto)"
                    log = f"{kg:,.0f} kg ÷ 28.000 = <span class='cr'>{cam} cam</span>"
                else:
                    tag = f"BULTOS PESADOS ({kpp:,.0f} kg/bto)"
                    log = f"{kg:,.0f} kg ÷ 28.500 = <span class='cr'>{cam} cam</span>"

                calc_cards.append({
                    "id": s.document_id,
                    "fecha": s.shipment_date.strftime("%d/%m/%Y") if s.shipment_date else "—",
                    "tag": tag,
                    "log": log
                })

                docs_list.append({
                    "id": s.document_id,
                    "fecha": s.shipment_date.strftime("%d/%m/%Y") if s.shipment_date else "—",
                    "kg": kg,
                    "bultos": bultos,
                    "cam": cam,
                    "flete": flete
                })

            mercaterias_list = sorted(list(mercaderias_set))[:3] if mercaderias_set else ["MERCADERÍA GENERAL"]

            match_res = {
                "source": "SIN_MATCH",
                "is_recent_90d": False,
                "match_type": "EXACTO",
                "score": 6,
                "score_dots": [True, True, True, True, True, True, False],
                "sale_price_usd": 3050.0,
                "cost_price_usd": 2400.0,
                "ruta_orig": "ROSARIO",
                "ruta_dest": "SANTIAGO",
                "ruta_paso": "LIBERTADORES",
                "ruta_merc": mercaterias_list[0]
            }

            if first_ship:
                orig_name = first_ship.origin_str or "ROSARIO"
                dest_name = first_ship.destination_str or "SANTIAGO"
                if first_ship.border_crossing:
                    paso_name = first_ship.border_crossing

                co = get_coords(orig_name)
                cd = get_coords(dest_name)
                if co[0]: orig_coords = co
                if cd[0]: dest_coords = cd

                match_res = MatchingEngine.match_shipment_to_routes_and_tariffs(
                    shipment_origin_lat=co[0], shipment_origin_lon=co[1],
                    shipment_dest_lat=cd[0], shipment_dest_lon=cd[1],
                    shipment_border_crossing=paso_name,
                    shipment_category=first_ship.category or "Otros",
                    routes=routes, tariffs=tariffs
                )

            mercotruck_price = match_res.get("sale_price_usd") or (comp_price * 0.9 if comp_price > 0 else 3050.0)
            is_recent = match_res.get("is_recent_90d", False)
            match_type = match_res.get("match_type", "EXACTO")

            diff_usd = (comp_price - mercotruck_price) if (comp_price > 0 and mercotruck_price) else 350.0
            diff_pct = round((diff_usd / comp_price) * 100) if (comp_price > 0 and diff_usd) else 10

            monthly_savings = max(0, int(diff_usd * p.total_trucks))

            opportunity_score = int(p.total_trucks * (diff_pct if diff_pct > 0 else 5))

            dias_inactivo = (today - last_date).days if last_date else 30
            if dias_inactivo <= 60:
                recency_color = "var(--green-tx)"
            elif dias_inactivo <= 120:
                recency_color = "#9A6000"
            else:
                recency_color = "var(--red)"

            fuente_val = p.fuente.value if hasattr(p.fuente, "value") else str(p.fuente)
            status_val = p.status.value if hasattr(p.status, "value") else str(p.status)

            first_word = p.name.split()[0]
            script = f'"Buenos días, le contacto de Mercotruck. Detectamos que {first_word} opera {p.total_trucks} camiones/mes hacia {dest_name} vía {paso_name}. Podemos ofrecerles U$S {mercotruck_price:,.0f}/cam — un {abs(diff_pct)}% menos que el mercado actual — con seguimiento satelital, disponibilidad garantizada en temporada invernal y coordinación aduanera incluida. ¿Tienen 15 minutos esta semana para una presentación?"'

            country_code = "CHILE"
            d_upper = dest_name.upper()
            if "BRASIL" in d_upper or "PORTO ALEGRE" in d_upper or "SAO PAULO" in d_upper or "CURITIBA" in d_upper:
                country_code = "BRASIL"
            elif "URUGUAY" in d_upper or "MONTEVIDEO" in d_upper or "FRAY BENTOS" in d_upper:
                country_code = "URUGUAY"
            elif "PARAGUAY" in d_upper or "ASUNCION" in d_upper or "CLORINDA" in d_upper:
                country_code = "PARAGUAY"

            p_dict = {
                "id": p.id,
                "name": p.name,
                "tax_id": p.tax_id or "—",
                "fuente": fuente_val,
                "category": p.primary_category or "Otros",
                "total_trucks": p.total_trucks,
                "avg_freight_per_truck_usd": comp_price,
                "mercotruck_price_usd": mercotruck_price,
                "diff_pct": diff_pct,
                "diff_usd": diff_usd,
                "monthly_savings": monthly_savings,
                "opportunity_score": opportunity_score,
                "is_recent_90d": is_recent,
                "status": status_val,
                "origin_str": orig_name,
                "destination_str": dest_name,
                "border_crossing": paso_name,
                "carrier_name": carrier_name,
                "mercaderias": mercaterias_list,
                "country": country_code,
                "match_type": match_type,
                "score": match_res.get("score", 6),
                "score_dots": match_res.get("score_dots", [True]*6 + [False]),
                "ruta_orig": match_res.get("ruta_orig", orig_name),
                "ruta_dest": match_res.get("ruta_dest", dest_name),
                "ruta_paso": match_res.get("ruta_paso", paso_name),
                "ruta_merc": match_res.get("ruta_merc", mercaterias_list[0]),
                "dias_inactivo": dias_inactivo,
                "recency_color": recency_color,
                "docs": docs_list[:10],
                "docs_count": len(docs_list),
                "calc_cards": calc_cards[:3],
                "script": script,
                "origin_lat": orig_coords[0],
                "origin_lon": orig_coords[1],
                "dest_lat": dest_coords[0],
                "dest_lon": dest_coords[1],
            }
            p_dict["encoded_json"] = quote(json.dumps({
                "id": p.id, "name": p.name, "tax_id": p.tax_id, "fuente": fuente_val,
                "total_trucks": p.total_trucks, "origin_str": orig_name, "destination_str": dest_name
            }))
            items.append(p_dict)

        # Primary Sorting: EXACTO matches first, then Opportunity Score DESC, then total_trucks DESC
        items.sort(key=lambda x: (0 if x["match_type"] == "EXACTO" else 1, -x["opportunity_score"], -x["total_trucks"]))

        _EVALUATED_PROSPECTS_CACHE = items
        _LAST_EVAL_CACHE_TIME = now

    return _EVALUATED_PROSPECTS_CACHE

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
    country: Optional[str] = Query(None),
    match: Optional[str] = Query(None),
    min_trucks: int = Query(1, ge=1),
    truck_capacity_kg: float = Query(28500.0, gt=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    all_evaluated = await get_all_evaluated_prospects_cache(db)

    s_search = search.lower().strip() if isinstance(search, str) and search.strip() else None
    s_origin = origin.lower().strip() if isinstance(origin, str) and origin.strip() else None
    s_dest = destination.lower().strip() if isinstance(destination, str) and destination.strip() else None
    s_prod = product.lower().strip() if isinstance(product, str) and product.strip() else None
    s_cat = category.strip() if isinstance(category, str) and category.strip() and category != "TODAS" else None
    s_fuente = fuente.strip() if isinstance(fuente, str) and fuente.strip() and fuente != "TODAS" else None
    s_status = status.strip() if isinstance(status, str) and status.strip() and status != "TODOS" else None
    s_country = country.upper().strip() if isinstance(country, str) and country.strip() and country.upper() != "TODOS" else None
    s_match = match.upper().strip() if isinstance(match, str) and match.strip() and match.upper() != "TODOS" else None

    filtered = []
    exact_count = 0
    near_count = 0
    total_savings_usd = 0
    total_trucks_all = 0
    total_freight_all = 0.0

    for item in all_evaluated:
        if item["match_type"] == "EXACTO": exact_count += 1
        else: near_count += 1
        total_savings_usd += item["monthly_savings"]
        total_trucks_all += item["total_trucks"]
        total_freight_all += item["avg_freight_per_truck_usd"] * item["total_trucks"]

        if s_country and item["country"] != s_country: continue
        if s_match and item["match_type"] != s_match: continue
        if min_trucks > 1 and item["total_trucks"] < min_trucks: continue
        if s_fuente and item["fuente"] != s_fuente: continue
        if s_status and item["status"] != s_status: continue
        if s_cat and item["category"] != s_cat: continue
        
        if s_search and (s_search not in item["name"].lower() and s_search not in item["tax_id"].lower()):
            continue
        if s_origin and s_origin not in item["origin_str"].lower():
            continue
        if s_dest and s_dest not in item["destination_str"].lower():
            continue
        if s_prod and not any(s_prod in m.lower() for m in item["mercaderias"]):
            continue

        filtered.append(item)

    # Sort EXACTO matches first, then Opportunity Score
    filtered.sort(key=lambda x: (0 if x["match_type"] == "EXACTO" else 1, -x["opportunity_score"], -x["total_trucks"]))

    total_filtered = len(filtered)
    tot_pages = (total_filtered + page_size - 1) // page_size if total_filtered > 0 else 1
    offset = (page - 1) * page_size
    page_items = filtered[offset:offset + page_size]

    categories = sorted(list(set(x["category"] for x in all_evaluated if x.get("category"))))
    distinct_origins = sorted(list(set(x["origin_str"] for x in all_evaluated if x.get("origin_str"))))
    distinct_destinations = sorted(list(set(x["destination_str"] for x in all_evaluated if x.get("destination_str"))))
    distinct_products = sorted(list(set(m for x in all_evaluated for m in x.get("mercaderias", []))))
    distinct_companies = sorted(list(set(x["name"] for x in all_evaluated if x.get("name"))))

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "prospects": page_items,
            "total": total_filtered,
            "page": page,
            "page_size": page_size,
            "total_pages": tot_pages,
            "stats": {
                "total_prospects": total_filtered,
                "exact_count": exact_count,
                "near_count": near_count,
                "total_trucks": total_trucks_all,
                "total_savings_usd": f"${total_savings_usd:,.0f}",
                "total_freight_usd": f"${total_freight_all:,.0f}"
            },
            "categories": categories,
            "distinct_origins": distinct_origins,
            "distinct_destinations": distinct_destinations,
            "distinct_products": distinct_products,
            "distinct_companies": distinct_companies,
            "filters": {
                "search": search or "",
                "origin": origin or "",
                "destination": destination or "",
                "product": product or "",
                "category": category or "TODAS",
                "fuente": fuente or "TODAS",
                "status": status or "TODOS",
                "country": country or "TODOS",
                "match": match or "TODOS",
                "min_trucks": min_trucks,
                "truck_capacity_kg": 28500.0
            }
        }
    )
