import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import List, Dict, Any
from app.domain.services.geo_service import get_coords

def parsear_monto(val) -> float:
    """Parsea montos numéricos limpios a float en USD."""
    if pd.isna(val) or val is None:
        return 0.0
    s = str(val).replace('$', '').replace(',', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0

def parse_historico_excel(file_path: str) -> List[Dict[str, Any]]:
    """Lee y limpia el archivo HISTORICO_MERCOTRUCK.xlsx utilizando los montos en USD (VENTA y COMPRA)."""
    df = pd.read_excel(file_path, sheet_name=0, engine='openpyxl')
    df.columns = [str(c).strip().upper() for c in df.columns]
    
    # Filtrar embarques confirmados
    if 'ESTADO' in df.columns:
        df = df[df['ESTADO'].astype(str).str.strip().str.upper() == 'EMBARQUE CONFIRMADO'].copy()
        
    routes = []
    for _, row in df.iterrows():
        origen = str(row.get('ORIGEN', '')).strip()
        destino = str(row.get('DESTINO', '')).strip()
        paso = str(row.get('PASO FRONTERIZO', '')).strip()
        
        if not origen or origen.lower() in ('nan', 'none', ''):
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
        
        # VENTA y COMPRA contienen los precios directos en USD por camión
        venta = parsear_monto(row.get('VENTA', 0))
        compra = parsear_monto(row.get('COMPRA', 0))
        
        if venta <= 0:
            continue
            
        renta = parsear_monto(row.get('RENTA BRUTA', 0))
        if renta == 0 and venta > 0 and compra > 0:
            renta = venta - compra
            
        pct_renta = parsear_monto(row.get('% RENTA BRUTA', 0))
        if pct_renta == 0 and venta > 0:
            pct_renta = round((renta / venta) * 100.0, 2)
            
        routes.append({
            "trip_date": fecha,
            "origin": origen,
            "destination": destino,
            "border_crossing": paso if paso and paso.lower() != 'nan' else None,
            "client_name": str(row.get('CLIENTE', '')).strip(),
            "shipper_name": str(row.get('SHIPPER', '')).strip(),
            "carrier_name": str(row.get('FLETERO', '')).strip(),
            "merchandise": str(row.get('MERCADERIA', '')).strip(),
            "sale_price_usd": venta,
            "cost_price_usd": compra,
            "gross_margin_usd": renta,
            "gross_margin_pct": pct_renta,
            "commercial_name": str(row.get('COMERCIAL', '')).strip(),
            "customer_name": str(row.get('CUSTOMER', '')).strip(),
            "status": str(row.get('ESTADO', 'EMBARQUE CONFIRMADO')).strip(),
            "origin_lat": co[0],
            "origin_lon": co[1],
            "dest_lat": cd[0],
            "dest_lon": cd[1],
        })
        
    return routes
