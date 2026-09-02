import re
from typing import Dict, Any, List, Optional, Tuple
from app.domain.services.geo_service import ADUANAS

def clean_company_name(name: str) -> str:
    """Normaliza y limpia el nombre corporativo eliminando sufijos legales y caracteres especiales."""
    if not name or str(name).strip().lower() in ('nan', 'none', '', 'no disponible', 'n/d'):
        return ''
    s = str(name).upper().strip()
    noise_patterns = [
        r'\bS\.A\.I\.C\.?\b', r'\bS\.A\.C\.?\b', r'\bS\.A\.?\b', r'\bSA\b', r'\bSPA\b',
        r'\bLTDA\.?\b', r'\bLIMITADA\b', r'\bINC\.?\b', r'\bSOCIEDAD\s+ANONIMA\b',
        r'\bCHILE\b', r'\bARGENTINA\b', r'\bBRASIL\b', r'\bURUGUAY\b', r'\bPARAGUAY\b',
        r'\bEMPRESAS\b', r'\bDISTRIBUIDORA\b', r'\bCOMERCIALIZADORA\b', r'\bIMPORTADORA\b'
    ]
    for pattern in noise_patterns:
        s = re.sub(pattern, '', s, flags=re.IGNORECASE)
    cleaned = re.sub(r'[^A-Z0-9]', '', s)
    return cleaned

# Clústeres agroindustriales por categoría de mercadería
AGRO_INDUSTRIAL_ORIGINS = {
    'Cereales y harinas': 'ROSARIO',
    'Aceites y grasas': 'SAN LORENZO',
    'Metales y siderurgia': 'VILLA CONSTITUCION',
    'Papel y cartón': 'PARANA',
    'Farmacia y salud': 'BUENOS AIRES',
    'Químicos industriales': 'SAN LORENZO',
    'Carnes y derivados': 'BUENOS AIRES',
    'Salmon y pesca': 'PUERTO MONTT',
    'Vinos y bebidas': 'MENDOZA',
    'Bebidas': 'MENDOZA',
    'Frutas y verduras': 'MENDOZA'
}

def infer_shipment_route(
    shipment_data: Dict[str, Any],
    historic_entity_map: Dict[str, Dict[str, Any]],
    routes_cache: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Motor de Inferencia de Rutas de 4 Niveles:
    - Nivel 1: Match directo por entidad normalizada con Histórico Mercotruck.
    - Nivel 2: Inferencia por Clúster Agroindustrial y Mercadería.
    - Nivel 3: Desacoplamiento de Aduana Mendoza (038) vs Origen Físico Real.
    - Nivel 4: Pareja Comercial Enriquecida (Shipper ➔ Consignee).
    """
    fuente = shipment_data.get("fuente", "IMPO")
    prospect_name = shipment_data.get("prospect_name", "")
    raw_origin = shipment_data.get("origin_str") or "ROSARIO"
    raw_dest = shipment_data.get("destination_str") or "SANTIAGO"
    paso = shipment_data.get("border_crossing") or "LIBERTADORES"
    category = shipment_data.get("category") or "Otros"
    mercaderia = (shipment_data.get("merchandise_desc") or "").upper()
    doc_id = str(shipment_data.get("document_id") or "")

    clean_prospect = clean_company_name(prospect_name)
    
    real_origin = raw_origin
    real_dest = raw_dest
    shipper_name = "EXPORTADOR NO DECLARADO"
    consignee_name = prospect_name
    customs_code = "038 - MENDOZA" if "038" in doc_id or "MENDOZA" in raw_origin.upper() else f"ADUANA {raw_origin}"
    inference_level = "RAW_CUSTOMS"
    certainty_badge = "⚪ Origen Declarado Aduana"

    cod3 = doc_id[:3] if len(doc_id) >= 3 else None

    # --- NIVEL 1: Vínculo Directo con Histórico Mercotruck ---
    historic_match = None
    if clean_prospect and clean_prospect in historic_entity_map:
        historic_match = historic_entity_map[clean_prospect]
    else:
        # Búsqueda parcial por subcadena
        for h_key, h_data in historic_entity_map.items():
            if len(h_key) >= 4 and (h_key in clean_prospect or clean_prospect in h_key):
                historic_match = h_data
                break

    if historic_match:
        real_origin = historic_match.get("origin") or real_origin
        real_dest = historic_match.get("destination") or real_dest
        shipper_name = historic_match.get("shipper") or shipper_name
        consignee_name = historic_match.get("customer") or consignee_name
        inference_level = "HISTORIC_MATCH"
        certainty_badge = "🟢 Verificado por Histórico Mercotruck"

    # --- NIVEL 2: Desacoplamiento de Tránsito Mendoza por Aduana Emisora del Interior ---
    elif cod3 and cod3 in ADUANAS and cod3 not in ("038", "016") and (
        "MENDOZA" in raw_origin.upper() or "LIBERTADORES" in raw_origin.upper() or raw_origin.upper() in ("OTROS ARGENTINA", "DESCONOCIDO", "")
    ):
        real_origin = ADUANAS[cod3][0].upper()
        inference_level = "CUSTOMS_DISPATCH_ORIGIN"
        certainty_badge = f"🟡 Origen Aduana Emisora ({real_origin})"

    # --- NIVEL 3: Inferencia por Clúster Agroindustrial & Mercadería ---
    elif "038" in doc_id or "MENDOZA" in raw_origin.upper() or raw_origin.upper() in ("OTROS ARGENTINA", "DESCONOCIDO", "LIBERTADORES"):
        # Verificar si la mercadería NO es de la región cuyana (vino/frutas)
        is_cuyo_product = any(kw in mercaderia for kw in ["VINO", "FRUTA", "TOMATE", "ACEITUNA", "MOSTOS", "CONSERVA"])
        
        if not is_cuyo_product:
            if category in AGRO_INDUSTRIAL_ORIGINS:
                real_origin = AGRO_INDUSTRIAL_ORIGINS[category]
                inference_level = "MERCHANDISE_RULE"
                certainty_badge = f"🟡 Inferencia Clúster ({real_origin})"
            elif any(kw in mercaderia for kw in ["HARINA", "TRIGO", "MAIZ", "SOJA", "ACEITE"]):
                real_origin = "SAN LORENZO"
                inference_level = "MERCHANDISE_RULE"
                certainty_badge = "🟡 Inferencia Clúster Cerealero (San Lorenzo)"
            elif any(kw in mercaderia for kw in ["CARNE", "VACUNO", "FIAMBRE", "POLLO"]):
                real_origin = "BUENOS AIRES"
                inference_level = "MERCHANDISE_RULE"
                certainty_badge = "🟡 Inferencia Clúster Frigorífico (Bs.As.)"

    # --- Desacoplamiento y Rotulación de Aduana de Cruce ---
    if cod3 and cod3 in ADUANAS:
        aduana_nombre = ADUANAS[cod3][0].upper()
        if cod3 in ("038", "016"):
            customs_code = f"{cod3} - ADUANA MENDOZA (Tránsito Cristo Redentor)"
        else:
            customs_code = f"{cod3} - ADUANA {aduana_nombre}"
    elif "038" in doc_id or "MENDOZA" in raw_origin.upper():
        customs_code = "038 - ADUANA MENDOZA (Tránsito Cristo Redentor)"

    return {
        "real_origin_city": real_origin,
        "real_destination_city": real_dest,
        "customs_office_code": customs_code,
        "shipper_name": shipper_name,
        "consignee_name": consignee_name,
        "geo_inference_level": inference_level,
        "certainty_badge": certainty_badge
    }
