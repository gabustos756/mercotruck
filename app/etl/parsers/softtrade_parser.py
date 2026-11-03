import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any
from app.domain.services.geo_service import resolver_origen_impo, get_coords
from app.domain.services.pricing_engine import PricingEngine

from app.domain.services.merchandise_service import (
    categorizar_mercaderia,
    clean_product_name,
    CATEGORIAS_DEFINICION as MERC_CATEGORIAS
)


def _safe_str(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "null") else s


def parse_softtrade_impo(file_path: str) -> List[Dict[str, Any]]:
    """
    Lee y limpia SOFTTRADE_IMPO.xlsx (Importaciones Argentina -> Chile) aplicando:
    - Desduplicación de Bultos de cabecera por (Documento de Transporte, Ordinal) antes de sumar al CRT.
    - Exclusión estricta de LTL / consolidados (Regla 1 de Matías Palomino).
    - Cálculo exacto de camiones FTL por peso (<= 28,5 tn) y estiba (piso, <=56 remontados, >56 cajas vs pallets).
    - Rescate de CRTs multi-camión (> U$S 8.000 totales) validando cordura por camión individual.
    """
    df = pd.read_excel(file_path, sheet_name='Detalle', engine='openpyxl', dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    df['_emp'] = df['Importador'].astype(str).str.strip()
    invalidos = {'', 'nan', 'none', 'no disponible', 'no determinado', 'nd', 'n/d'}
    df = df[~df['_emp'].str.lower().isin(invalidos) & (df['_emp'].str.len() > 2)].copy()

    df['_kg'] = pd.to_numeric(df['Kgs. Brutos'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)
    df['_flete'] = pd.to_numeric(df['Flete U$S'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)
    df['_fob'] = pd.to_numeric(df['FOB U$S'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)
    df['_cif'] = pd.to_numeric(df['U$S CIF'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)
    df['_fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.date
    df['_doc'] = df['Documento de Transporte'].astype(str).str.strip()

    if 'Bultos' in df.columns:
        df['_bultos'] = pd.to_numeric(df['Bultos'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)
    else:
        df['_bultos'] = 0.0

    if 'Ordinal' in df.columns:
        df['_ord'] = df['Ordinal'].astype(str).str.strip()
    else:
        df['_ord'] = "1"

    if 'Incoterm' in df.columns:
        df['_incoterm'] = df['Incoterm'].astype(str).str.strip().str.upper()
    else:
        df['_incoterm'] = "CYS"

    # Paso 1: Agrupar por (CRT, Ordinal) para desduplicar Bultos (campo de cabecera DIN repetido en cada ítem)
    # mientras se suman Kgs. Brutos y Flete U$S que sí vienen prorrateados por ítem arancelario.
    by_ordinal = df.groupby(['_doc', '_ord'], as_index=False).agg(
        empresa=('Importador', 'first'),
        rut=('RUT', 'first'),
        transportista=('Transportista', 'first'),
        puerto_embarque=('Puerto de Embarque', 'first'),
        paso=('Puerto de Desembarque', 'first'),
        destino_str=('Aduana', 'first'),
        bultos=('_bultos', 'first'),
        kg=('_kg', 'sum'),
        flete=('_flete', 'sum'),
        fob=('_fob', 'sum'),
        cif=('_cif', 'sum'),
        fecha=('_fecha', 'max'),
        mercaderia=('Mercadería', 'first'),
        sach=('Código SACH', 'first'),
        item=('item', 'first'),
        incoterm=('_incoterm', 'first'),
    )

    # Paso 2: Consolidar al nivel físico del camión / Documento de Transporte (CRT)
    docs = by_ordinal.groupby('_doc', as_index=False).agg(
        empresa=('empresa', 'first'),
        rut=('rut', 'first'),
        transportista=('transportista', 'first'),
        puerto_embarque=('puerto_embarque', 'first'),
        paso=('paso', 'first'),
        destino_str=('destino_str', 'first'),
        bultos=('bultos', 'sum'),
        kg=('kg', 'sum'),
        flete=('flete', 'sum'),
        fob=('fob', 'sum'),
        cif=('cif', 'sum'),
        fecha=('fecha', 'max'),
        mercaderia=('mercaderia', 'first'),
        sach=('sach', 'first'),
        item=('item', 'first'),
        incoterm=('incoterm', 'first'),
    ).rename(columns={'_doc': 'documento'})

    shipments = []
    for _, row in docs.iterrows():
        kg = float(row['kg'] or 0.0)
        bultos = int(round(float(row['bultos'] or 0.0)))
        flete_total = float(row['flete'] or 0.0)

        eval_ftl = PricingEngine.evaluate_ftl_shipment(
            gross_weight_kg=kg,
            bultos=bultos,
            freight_total_usd=flete_total,
            fuente="IMPO",
        )
        if not eval_ftl["is_ftl"]:
            continue

        origen_str = resolver_origen_impo(_safe_str(row['puerto_embarque']), "", _safe_str(row['documento']))
        trucks = eval_ftl["trucks_count"]
        raw_cam = eval_ftl["raw_freight_per_truck_usd"]
        incoterm_str = _safe_str(row['incoterm']) or "CYS"
        real_cam = PricingEngine.calibrate_real_freight_usd(
            raw_freight_per_truck_usd=raw_cam,
            incoterm=incoterm_str,
            origin_str=origen_str,
            fuente="IMPO",
        )

        merc_raw = _safe_str(row['mercaderia'])
        cat = categorizar_mercaderia(merc_raw)
        prod_clean = clean_product_name(merc_raw)
        eq_type = PricingEngine.classify_equipment(merchandise_desc=merc_raw, category=cat)

        shipments.append({
            "fuente": "IMPO",
            "prospect_name": _safe_str(row['empresa']),
            "prospect_tax_id": _safe_str(row['rut']) or None,
            "document_id": _safe_str(row['documento']),
            "item": _safe_str(row['item']) or None,
            "shipment_date": row['fecha'] if pd.notna(row['fecha']) else None,
            "customs_sach_code": _safe_str(row['sach']) or None,
            "customs_office": _safe_str(row['destino_str']),
            "origin_str": origen_str,
            "destination_str": _safe_str(row['destino_str']),
            "border_crossing": _safe_str(row['paso']) or None,
            "carrier_name": _safe_str(row['transportista']) or None,
            "gross_weight_kg": kg,
            "bultos_count": bultos,
            "trucks_count": trucks,
            "freight_usd": flete_total,
            "raw_freight_per_truck_usd": raw_cam,
            "estimated_real_freight_per_truck_usd": real_cam,
            "freight_per_truck_usd": real_cam,
            "incoterm": incoterm_str,
            "equipment_type": eq_type,
            "stowage_type": eval_ftl["stowage_type"],
            "fob_usd": float(row['fob'] or 0.0),
            "cif_usd": float(row['cif'] or 0.0),
            "merchandise_desc": merc_raw or None,
            "product_clean": prod_clean,
            "category": cat,
        })
    return shipments


def parse_softtrade_expo(file_path: str) -> List[Dict[str, Any]]:
    """Lee y limpia SOFTTRADE_EXPO.xlsx (Exportaciones Chile -> Argentina) excluyendo LTL."""
    df = pd.read_excel(file_path, sheet_name='Detalle', engine='openpyxl', dtype=str)
    df.columns = [str(c).strip() for c in df.columns]

    df['_emp'] = df['Exportador'].astype(str).str.strip()
    invalidos = {'', 'nan', 'none', 'no disponible', 'no determinado', 'nd', 'n/d'}
    df = df[~df['_emp'].str.lower().isin(invalidos) & (df['_emp'].str.len() > 2)].copy()

    df['_kg'] = pd.to_numeric(df['Kgs. Brutos'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)
    df['_flete'] = pd.to_numeric(df['Flete U$S'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)
    df['_fob'] = pd.to_numeric(df['U$S FOB'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)
    df['_cif'] = pd.to_numeric(df['CIF U$S'].astype(str).str.replace(',', '.', regex=False), errors='coerce').fillna(0.0)
    df['_fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.date

    if 'Cláusula VTA.' in df.columns:
        df['_incoterm'] = df['Cláusula VTA.'].astype(str).str.strip().str.upper()
    else:
        df['_incoterm'] = "CFR"

    docs = df.groupby('DUA', as_index=False).agg(
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
        item=('item', 'first'),
        incoterm=('_incoterm', 'first'),
    ).rename(columns={'DUA': 'documento'})

    shipments = []
    for _, row in docs.iterrows():
        kg = float(row['kg'] or 0.0)
        flete_total = float(row['flete'] or 0.0)

        eval_ftl = PricingEngine.evaluate_ftl_shipment(
            gross_weight_kg=kg,
            bultos=0,
            freight_total_usd=flete_total,
            fuente="EXPO",
        )
        if not eval_ftl["is_ftl"]:
            continue

        trucks = eval_ftl["trucks_count"]
        raw_cam = eval_ftl["raw_freight_per_truck_usd"]
        incoterm_str = _safe_str(row['incoterm']) or "CFR"
        real_cam = PricingEngine.calibrate_real_freight_usd(
            raw_freight_per_truck_usd=raw_cam,
            incoterm=incoterm_str,
            origin_str=_safe_str(row['origen_str']),
            fuente="EXPO",
        )

        merc_raw = _safe_str(row['mercaderia'])
        cat = categorizar_mercaderia(merc_raw)
        prod_clean = clean_product_name(merc_raw)
        eq_type = PricingEngine.classify_equipment(merchandise_desc=merc_raw, category=cat)

        shipments.append({
            "fuente": "EXPO",
            "prospect_name": _safe_str(row['empresa']),
            "prospect_tax_id": None,
            "document_id": _safe_str(row['documento']),
            "item": _safe_str(row['item']) or None,
            "shipment_date": row['fecha'] if pd.notna(row['fecha']) else None,
            "customs_sach_code": _safe_str(row['sach']) or None,
            "customs_office": _safe_str(row['origen_str']),
            "origin_str": _safe_str(row['origen_str']),
            "destination_str": _safe_str(row['destino_str']),
            "border_crossing": _safe_str(row['paso']) or None,
            "carrier_name": _safe_str(row['transportista']) or None,
            "gross_weight_kg": kg,
            "bultos_count": 0,
            "trucks_count": trucks,
            "freight_usd": flete_total,
            "raw_freight_per_truck_usd": raw_cam,
            "estimated_real_freight_per_truck_usd": real_cam,
            "freight_per_truck_usd": real_cam,
            "incoterm": incoterm_str,
            "equipment_type": eq_type,
            "stowage_type": eval_ftl["stowage_type"],
            "fob_usd": float(row['fob'] or 0.0),
            "cif_usd": float(row['cif'] or 0.0),
            "merchandise_desc": merc_raw or None,
            "product_clean": prod_clean,
            "category": cat,
        })
    return shipments
