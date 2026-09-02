import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Tuple
from app.domain.services.geo_service import resolver_origen_impo, get_coords
from app.domain.services.pricing_engine import PricingEngine

from app.domain.services.merchandise_service import (
    categorizar_mercaderia,
    clean_product_name,
    CATEGORIAS_DEFINICION as MERC_CATEGORIAS
)

def parse_softtrade_impo(file_path: str) -> List[Dict[str, Any]]:
    """Lee y limpia SOFTTRADE_IMPO.xlsx (Importaciones Argentina -> Chile)."""
    df = pd.read_excel(file_path, sheet_name='Detalle', engine='openpyxl', dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    
    df['_emp'] = df['Importador'].astype(str).str.strip()
    invalidos = {'', 'nan', 'none', 'no disponible', 'no determinado', 'nd', 'n/d'}
    df = df[~df['_emp'].str.lower().isin(invalidos) & (df['_emp'].str.len() > 2)].copy()
    
    df['_kg'] = pd.to_numeric(df['Kgs. Brutos'].str.replace(',', '.', regex=False), errors='coerce').fillna(0)
    df['_flete'] = pd.to_numeric(df['Flete U$S'].str.replace(',', '.', regex=False), errors='coerce').fillna(0)
    df['_fob'] = pd.to_numeric(df['FOB U$S'].str.replace(',', '.', regex=False), errors='coerce').fillna(0)
    df['_cif'] = pd.to_numeric(df['U$S CIF'].str.replace(',', '.', regex=False), errors='coerce').fillna(0)
    df['_fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.date
    df['_doc'] = df['Documento de Transporte'].astype(str).str.strip()
    
    # Agrupar por documento
    docs = df.groupby('_doc').agg(
        empresa=('Importador', 'first'),
        rut=('RUT', 'first'),
        transportista=('Transportista', 'first'),
        puerto_embarque=('Puerto de Embarque', 'first'),
        paso=('Puerto de Desembarque', 'first'),
        destino_str=('Aduana', 'first'),
        kg=('_kg', 'sum'),
        flete=('_flete', 'sum'),
        fob=('_fob', 'sum'),
        cif=('_cif', 'sum'),
        fecha=('_fecha', 'max'),
        mercaderia=('Mercadería', 'first'),
        sach=('Código SACH', 'first'),
        item=('item', 'first')
    ).reset_index().rename(columns={'_doc': 'documento'})
    
    # Filtro de flete razonable ($500 - $8000)
    docs = docs[(docs['flete'] >= 500) & (docs['flete'] <= 8000)].copy()
    
    shipments = []
    for _, row in docs.iterrows():
        origen_str = resolver_origen_impo(str(row['puerto_embarque'] or ''), "", str(row['documento'] or ''))
        kg = float(row['kg'])
        trucks = PricingEngine.calculate_trucks(kg)
        flete_total = float(row['flete'])
        flete_cam = round(flete_total / trucks, 2)
        cat = categorizar_mercaderia(row['mercaderia'])
        prod_clean = clean_product_name(row['mercaderia'])
        
        shipments.append({
            "fuente": "IMPO",
            "prospect_name": str(row['empresa']).strip(),
            "prospect_tax_id": str(row['rut']).strip() if pd.notna(row['rut']) else None,
            "document_id": str(row['documento']),
            "item": str(row['item']) if pd.notna(row['item']) else None,
            "shipment_date": row['fecha'] if pd.notna(row['fecha']) else None,
            "customs_sach_code": str(row['sach']) if pd.notna(row['sach']) else None,
            "customs_office": str(row['destino_str']).strip(),
            "origin_str": origen_str,
            "destination_str": str(row['destino_str']).strip(),
            "border_crossing": str(row['paso']).strip() if pd.notna(row['paso']) else None,
            "carrier_name": str(row['transportista']).strip() if pd.notna(row['transportista']) else None,
            "gross_weight_kg": kg,
            "trucks_count": trucks,
            "freight_usd": flete_total,
            "freight_per_truck_usd": flete_cam,
            "fob_usd": float(row['fob']),
            "cif_usd": float(row['cif']),
            "merchandise_desc": str(row['mercaderia']).strip() if pd.notna(row['mercaderia']) else None,
            "product_clean": prod_clean,
            "category": cat,
        })
    return shipments

def parse_softtrade_expo(file_path: str) -> List[Dict[str, Any]]:
    """Lee y limpia SOFTTRADE_EXPO.xlsx (Exportaciones Chile -> Argentina)."""
    df = pd.read_excel(file_path, sheet_name='Detalle', engine='openpyxl', dtype=str)
    df.columns = [str(c).strip() for c in df.columns]
    
    df['_emp'] = df['Exportador'].astype(str).str.strip()
    invalidos = {'', 'nan', 'none', 'no disponible', 'no determinado', 'nd', 'n/d'}
    df = df[~df['_emp'].str.lower().isin(invalidos) & (df['_emp'].str.len() > 2)].copy()
    
    df['_kg'] = pd.to_numeric(df['Kgs. Brutos'].str.replace(',', '.', regex=False), errors='coerce').fillna(0)
    df['_flete'] = pd.to_numeric(df['Flete U$S'].str.replace(',', '.', regex=False), errors='coerce').fillna(0)
    df['_fob'] = pd.to_numeric(df['U$S FOB'].str.replace(',', '.', regex=False), errors='coerce').fillna(0)
    df['_cif'] = pd.to_numeric(df['CIF U$S'].str.replace(',', '.', regex=False), errors='coerce').fillna(0)
    df['_fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.date
    
    docs = df.groupby('DUA').agg(
        empresa=('_emp', 'first'),
        transportista=('Empresa Transportista', 'first'),
        origen_str=('Aduana', 'first'),
        paso=('Puerto de Embarque', 'first'),
        destino_str=('Puerto de Desembarque', 'first'),
        kg=('_kg', 'sum'),
        flete=('_flete', 'sum'),
        fob=('_fob', 'sum'),
        cif=('_cif', 'sum'),
        fecha=('_fecha', 'max'),
        mercaderia=('Mercadería', 'first'),
        sach=('Código SACH', 'first'),
        item=('item', 'first')
    ).reset_index().rename(columns={'DUA': 'documento'})
    
    docs = docs[(docs['flete'] >= 500) & (docs['flete'] <= 8000)].copy()
    
    shipments = []
    for _, row in docs.iterrows():
        kg = float(row['kg'])
        trucks = PricingEngine.calculate_trucks(kg)
        flete_total = float(row['flete'])
        flete_cam = round(flete_total / trucks, 2)
        cat = categorizar_mercaderia(row['mercaderia'])
        prod_clean = clean_product_name(row['mercaderia'])
        
        shipments.append({
            "fuente": "EXPO",
            "prospect_name": str(row['empresa']).strip(),
            "prospect_tax_id": None,
            "document_id": str(row['documento']),
            "item": str(row['item']) if pd.notna(row['item']) else None,
            "shipment_date": row['fecha'] if pd.notna(row['fecha']) else None,
            "customs_sach_code": str(row['sach']) if pd.notna(row['sach']) else None,
            "customs_office": str(row['origen_str']).strip(),
            "origin_str": str(row['origen_str']).strip(),
            "destination_str": str(row['destino_str']).strip(),
            "border_crossing": str(row['paso']).strip() if pd.notna(row['paso']) else None,
            "carrier_name": str(row['transportista']).strip() if pd.notna(row['transportista']) else None,
            "gross_weight_kg": kg,
            "trucks_count": trucks,
            "freight_usd": flete_total,
            "freight_per_truck_usd": flete_cam,
            "fob_usd": float(row['fob']),
            "cif_usd": float(row['cif']),
            "merchandise_desc": str(row['mercaderia']).strip() if pd.notna(row['mercaderia']) else None,
            "product_clean": prod_clean,
            "category": cat,
        })
    return shipments
