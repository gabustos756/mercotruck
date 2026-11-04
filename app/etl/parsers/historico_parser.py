import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import List, Dict, Any
from app.domain.services.geo_service import get_coords
from app.domain.services.pricing_engine import PricingEngine
from app.domain.services.matching_engine import MatchingEngine


def parsear_monto(val) -> float:
    """Parsea montos numéricos limpios a float en USD."""
    if pd.isna(val) or val is None:
        return 0.0
    s = str(val).replace('$', '').replace(',', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def _clean_str(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "null") else s


def parse_historico_excel(file_path: str) -> List[Dict[str, Any]]:
    """
    Lee y limpia HISTORICO_MERCOTRUCK.xlsx utilizando VENTA y COMPRA en USD por camión,
    excluyendo camionetas chicas (TRUCKY) y clasificando tipo de equipo (SECO / FRIO / IMO).
    """
    df = pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
    df.columns = [str(c).strip().upper() for c in df.columns]

    # Filtrar embarques confirmados
    if 'ESTADO' in df.columns:
        df = df[df['ESTADO'].astype(str).str.strip().str.upper() == 'EMBARQUE CONFIRMADO'].copy()

    routes = []
    for _, row in df.iterrows():
        origen = _clean_str(row.get('ORIGEN', ''))
        destino = _clean_str(row.get('DESTINO', ''))
        paso = _clean_str(row.get('PASO FRONTERIZO', ''))
        unidad = _clean_str(row.get('UNIDAD', '')).upper()
        pack = _clean_str(row.get('PACK', '')).upper()
        imo_flag = _clean_str(row.get('IMO', '')).upper()
        mercaderia = _clean_str(row.get('MERCADERIA', ''))

        if not origen:
            continue

        # Excluir camionetas (TRUCKY) y cargas consolidadas/parciales (LTL) para no contaminar tarifas FTL 28,5 tn
        if any(x in unidad for x in ("TRUCKY", "CAMIONETA", "UTILITARIO", "CONSOLIDADO", "LTL", "PARCIAL")):
            continue
        if any(x in pack for x in ("CONSOLIDADO", "LTL", "PARCIAL")):
            continue

        fecha_raw = row.get('FECHA')
        fecha = None
        if pd.notna(fecha_raw):
            try:
                fecha = pd.to_datetime(fecha_raw, errors='coerce').date()
            except Exception:
                fecha = None

        co = get_coords(origen)
        cd = get_coords(destino)

        venta = parsear_monto(row.get('VENTA', 0))
        compra = parsear_monto(row.get('COMPRA', 0))

        # Descartar cobros accesorios (estadías, falsos fletes o tramos locales < U$S 950)
        if venta < 950.0:
            continue

        if co[0] and cd[0]:
            dist_km = MatchingEngine.haversine_km(co[0], co[1], cd[0], cd[1])
            if dist_km > 650.0 and venta < 1350.0:
                continue

        renta = parsear_monto(row.get('RENTA BRUTA', 0))
        if renta == 0 and venta > 0 and compra > 0:
            renta = venta - compra

        pct_renta = parsear_monto(row.get('% RENTA BRUTA', 0))
        if pct_renta == 0 and venta > 0:
            pct_renta = round((renta / venta) * 100.0, 2)

        equipment_type = PricingEngine.classify_equipment(
            merchandise_desc=mercaderia,
            unit_raw=unidad,
            imo_raw=imo_flag,
        )

        routes.append({
            "trip_date": fecha,
            "origin": origen,
            "destination": destino,
            "border_crossing": paso or None,
            "client_name": _clean_str(row.get('CLIENTE', '')),
            "shipper_name": _clean_str(row.get('SHIPPER', '')),
            "carrier_name": _clean_str(row.get('FLETERO', '')),
            "merchandise": mercaderia,
            "sale_price_usd": venta,
            "cost_price_usd": compra,
            "gross_margin_usd": renta,
            "gross_margin_pct": pct_renta,
            "commercial_name": _clean_str(row.get('COMERCIAL', '')),
            "customer_name": _clean_str(row.get('CUSTOMER', '')),
            "status": _clean_str(row.get('ESTADO', 'EMBARQUE CONFIRMADO')) or "EMBARQUE CONFIRMADO",
            "unit_type": unidad or "SEMIRREMOLQUE",
            "equipment_type": equipment_type,
            "pack_type": pack or None,
            "is_imo": imo_flag or "NO",
            "origin_lat": co[0],
            "origin_lon": co[1],
            "dest_lat": cd[0],
            "dest_lon": cd[1],
        })

    return routes
