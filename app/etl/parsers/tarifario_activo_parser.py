import os
import re
import statistics
import unicodedata
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import openpyxl

from app.domain.services.geo_service import get_coords
from app.domain.services.matching_engine import MatchingEngine
from app.domain.services.pricing_engine import PricingEngine
from app.etl.parsers.softtrade_parser import categorizar_mercaderia

DEFAULT_TARIFARIO_ACTIVO_PATH = "docs/Tarifario Activo Octubre - Actualidad.xlsx"

# Sufijos societarios/geográficos genéricos que no identifican por sí solos a una cuenta comercial
_CORP_STOPWORDS = {
    "SA", "SPA", "SRL", "LTDA", "LIMITADA", "INC", "CORP", "CIA", "COMPANIA",
    "SOCIEDAD", "ANONIMA", "COMERCIAL", "COMERCIALIZADORA", "DISTRIBUIDORA", "DIST",
    "IMPORTADORA", "IMP", "EXPORTADORA", "EXP", "INDUSTRIAL", "IND", "EMPRESAS",
    "INVERSIONES", "INV", "INMOBILIARIA", "INMOB", "AGRICOLA", "AGRIC", "AGROINDUSTRIAL",
    "CHILE", "ARGENTINA", "BRASIL", "URUGUAY", "PARAGUAY", "SUICE", "SUIZA",
    "DE", "DEL", "LA", "LAS", "EL", "LOS", "Y", "E",
}

# Alias corporativos verificados entre nombres comerciales del Tarifario Activo y razones sociales de Aduana
_EXPLICIT_CLIENT_ALIASES: Dict[str, str] = {
    "IRUZUN": "IRURZUN",
    "TRESMONTES": "LUCCHETTI",
    "TRESMONTES LUCCHETTI": "LUCCHETTI",
    "RENDIC HERMANOS": "SMU RENDIC",
    "SMU RENDIC": "SMU RENDIC",
    "GRUPO BUDEGUER": "BUDEGUER",
    "LEVADURAS COLLICO": "COLLICO",
}


def _strip_accents_upper(val: str) -> str:
    if not val:
        return ""
    s = str(val).strip().upper()
    s = s.replace("’", "'").replace("`", "'")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _tokenize_company(name: str) -> List[str]:
    s = _strip_accents_upper(name)
    if not s or s in ("NAN", "NONE", "N/A", "—", "-", "EXPORTADOR NO DECLARADO"):
        return []
    # Unificar abreviaturas S.A. / S.P.A. / S.R.L. antes de separar tokens
    s = re.sub(r"\bS\s*\.\s*A\s*\.\s*I\s*\.\s*C\.?\b", " SA ", s)
    s = re.sub(r"\bS\s*\.\s*A\s*\.\s*C\.?\b", " SA ", s)
    s = re.sub(r"\bS\s*\.\s*A\.?\b", " SA ", s)
    s = re.sub(r"\bS\s*\.\s*P\s*\.\s*A\.?\b", " SPA ", s)
    s = re.sub(r"\bS\s*\.\s*R\s*\.\s*L\.?\b", " SRL ", s)
    raw_tokens = [t for t in re.split(r"[^A-Z0-9&]+", s) if t]
    return raw_tokens


def _core_tokens(name: str) -> List[str]:
    tokens = _tokenize_company(name)
    core = [t for t in tokens if t not in _CORP_STOPWORDS]
    return core if core else tokens


def parse_tarifario_price_usd(val: Any) -> float:
    """Convierte montos como 'USD5.400,00', '$ 2.850,00' o floats a USD float limpio."""
    if val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val) if val > 0 else 0.0

    s = str(val).upper()
    s = s.replace("USD", "").replace("U$S", "").replace("US$", "").replace("$", "").strip()
    s = re.sub(r"\s+", "", s)
    if not s:
        return 0.0

    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        parts = s.split(",")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            s = s.replace(",", "")
        else:
            s = s.replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts) == 2 and len(parts[1]) == 3 and parts[1].isdigit():
            s = s.replace(".", "")

    try:
        v = float(s)
        return v if v > 0 else 0.0
    except ValueError:
        return 0.0


def format_tariff_location(raw_loc: str) -> str:
    """
    Normaliza ubicaciones del Tarifario Activo ('ARG - CÓRDOBA - GENERAL DEHEZA',
    'CL - LIBERTADOR GENERAL BERNARDO O’HIGGINS - PLACILLA') a un formato ejecutivo limpio
    que preserva provincia/región y ciudad exacta.
    """
    if not raw_loc:
        return ""
    norm = _strip_accents_upper(raw_loc)
    parts = [p.strip() for p in norm.split(" - ") if p.strip()]
    if len(parts) >= 3:
        country, prov, city = parts[0], parts[1], parts[-1]
        if country in ("CL", "CLP", "CHILE"):
            return f"CL - {city}"
        if country in ("PY", "PRY", "PARAGUAY"):
            return f"PY - {city}"
        if country in ("BR", "BRA", "BRASIL"):
            return f"BRA - {city}"
        if country in ("UY", "URY", "URUGUAY"):
            return f"UY - {city}"
        if prov == city:
            return city
        return f"{prov} - {city}"
    return norm


def normalize_border_name(raw_border: str) -> str:
    b = _strip_accents_upper(raw_border)
    if not b:
        return "LIBERTADORES"
    if "LIBERTADORES" in b or "CRISTO REDENTOR" in b:
        return "LIBERTADORES"
    if "PINO HACHADO" in b:
        return "PINO HACHADO"
    if "JAMA" in b:
        return "JAMA"
    if "SAMORE" in b:
        return "CARDENAL SAMORE"
    if "ENCARNACION" in b or "POSADAS" in b:
        return "ENCARNACION"
    return b


class ActiveClientMatcher:
    """
    Motor determinístico por tokens de palabras completas para identificar si una empresa
    pertenece al padrón de Clientes Activos de Mercotruck (evitando pisar cuentas vigentes
    y sin falsos positivos por subcadenas parciales como 'ALVAL' dentro de 'VALLE' o 'SMU' en 'SMURFIT').
    """

    def __init__(self, client_names: List[str]):
        # Lista de (canonical_label, tuple_of_core_tokens, compact_core_str)
        self.patterns: List[Tuple[str, Tuple[str, ...], str]] = []
        self.single_token_map: Dict[str, str] = {}
        seen = set()

        expanded_pairs: List[Tuple[str, str]] = []
        for raw in client_names:
            clean_disp = str(raw or "").strip()
            if not clean_disp:
                continue
            upper_disp = _strip_accents_upper(clean_disp)
            canonical = _EXPLICIT_CLIENT_ALIASES.get(upper_disp, clean_disp.upper().strip())
            expanded_pairs.append((raw, canonical))

        for alias_phrase, target_canonical in _EXPLICIT_CLIENT_ALIASES.items():
            expanded_pairs.append((alias_phrase, target_canonical))

        for raw_phrase, canonical in expanded_pairs:
            core = tuple(_core_tokens(raw_phrase))
            if not core:
                continue
            compact = "".join(core)
            if (core, canonical) in seen:
                continue
            seen.add((core, canonical))
            if len(core) == 1:
                tok = core[0]
                if len(tok) >= 3:
                    self.single_token_map.setdefault(tok, canonical)
            else:
                self.patterns.append((canonical, core, compact))

    def match_single_name(self, candidate: Optional[str]) -> Optional[str]:
        if not candidate:
            return None
        cand_core = _core_tokens(candidate)
        if not cand_core:
            return None
        cand_all_tokens = set(_tokenize_company(candidate))
        cand_core_set = set(cand_core)
        cand_compact = "".join(cand_core)

        # 1. Match de clientes de un solo token distintivo como palabra entera exacta (ej. PROSUD, SOPROLE, ICB, ALVAL)
        for tok in cand_core:
            if tok in self.single_token_map:
                # Evitar falsos positivos si el token es genérico solo cuando viene acompañado
                return self.single_token_map[tok]

        # 2. Match de clientes multi-palabra (todos los tokens núcleo presentes como palabras completas o secuencia compacta exacta)
        for canonical, pat_tokens, pat_compact in self.patterns:
            if all(pt in cand_core_set or pt in cand_all_tokens for pt in pat_tokens):
                return canonical
            if len(pat_compact) >= 6 and cand_compact == pat_compact:
                return canonical

        return None

    def match_entity(
        self,
        prospect_name: Optional[str] = None,
        trade_name: Optional[str] = None,
        shipper_name: Optional[str] = None,
    ) -> Optional[str]:
        """Retorna el nombre canónico del Cliente Activo Mercotruck si coincide, o None si es prospecto libre."""
        for field in (prospect_name, trade_name, shipper_name):
            hit = self.match_single_name(field)
            if hit:
                return hit
        return None


_CACHED_ACTIVE_MATCHER: Optional[ActiveClientMatcher] = None
_CACHED_MATCHER_MTIME: float = 0.0


def get_active_client_matcher(file_path: str = DEFAULT_TARIFARIO_ACTIVO_PATH) -> ActiveClientMatcher:
    """Obtiene en memoria (con recarga automática si cambia el Excel) el matcher de los clientes activos."""
    global _CACHED_ACTIVE_MATCHER, _CACHED_MATCHER_MTIME
    if not os.path.exists(file_path):
        return ActiveClientMatcher([])

    mtime = os.path.getmtime(file_path)
    if _CACHED_ACTIVE_MATCHER is None or mtime != _CACHED_MATCHER_MTIME:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
        ws = wb["base"] if "base" in wb.sheetnames else wb[wb.sheetnames[0]]
        clients: List[str] = []
        for idx, row in enumerate(ws.iter_rows(values_only=True)):
            if idx == 0 or not row:
                continue
            c = row[0]
            if c is not None and str(c).strip():
                clients.append(str(c).strip())
        wb.close()
        _CACHED_ACTIVE_MATCHER = ActiveClientMatcher(clients)
        _CACHED_MATCHER_MTIME = mtime

    return _CACHED_ACTIVE_MATCHER


def parse_tarifario_activo_excel(
    file_path: str = DEFAULT_TARIFARIO_ACTIVO_PATH,
    hist_routes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Lee 'Tarifario Activo Octubre - Actualidad.xlsx' y devuelve:
      - 'active_clients': lista única ordenada de clientes activos de Mercotruck
      - 'tariffs': lista depurada de tarifas maestras agrupadas por (origen, destino, paso, equipo)
      - 'client_routes': rutas activas por cliente para enriquecer inferencia geográfica
    """
    if not os.path.exists(file_path):
        return {"active_clients": [], "tariffs": [], "client_routes": []}

    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb["base"] if "base" in wb.sheetnames else wb[wb.sheetnames[0]]

    active_clients_set: Set[str] = set()
    corridor_groups: Dict[Tuple[str, str, str, str], Dict[str, Any]] = {}
    client_routes: List[Dict[str, Any]] = []

    for r_idx in range(2, ws.max_row + 1):
        client_raw = ws.cell(r_idx, 1).value
        merc_raw = ws.cell(r_idx, 2).value
        orig_raw = ws.cell(r_idx, 3).value
        paso_raw = ws.cell(r_idx, 4).value
        dest_raw = ws.cell(r_idx, 5).value
        price_raw = ws.cell(r_idx, 6).value

        client_str = str(client_raw).strip() if client_raw is not None else ""
        if client_str:
            active_clients_set.add(client_str)

        orig_str_raw = str(orig_raw).strip() if orig_raw is not None else ""
        dest_str_raw = str(dest_raw).strip() if dest_raw is not None else ""
        if not orig_str_raw or not dest_str_raw:
            continue

        sale_usd = parse_tarifario_price_usd(price_raw)
        if sale_usd <= 0:
            continue

        co = get_coords(orig_str_raw)
        cd = get_coords(dest_str_raw)

        # Filtrar ítems puntuales LTL/consolidados (< USD 1.350 en larga distancia > 650 km) para no contaminar FTL
        if sale_usd < 1100.0:
            continue
        if co[0] is not None and cd[0] is not None:
            dist_km = MatchingEngine.haversine_km(co[0], co[1], cd[0], cd[1])
            if dist_km > 650.0 and sale_usd < 1350.0:
                continue

        merc_str = str(merc_raw).strip() if merc_raw is not None else "Carga General"
        cat = categorizar_mercaderia(merc_str)
        eq = PricingEngine.classify_equipment(merchandise_desc=merc_str, category=cat)

        orig_fmt = format_tariff_location(orig_str_raw)
        dest_fmt = format_tariff_location(dest_str_raw)
        paso_fmt = normalize_border_name(str(paso_raw or "LIBERTADORES"))

        client_routes.append({
            "client_name": client_str,
            "origin": orig_fmt,
            "destination": dest_fmt,
            "border_crossing": paso_fmt,
            "merchandise": merc_str,
            "category": cat,
            "equipment_type": eq,
            "sale_price_usd": sale_usd,
            "origin_lat": co[0],
            "origin_lon": co[1],
            "dest_lat": cd[0],
            "dest_lon": cd[1],
        })

        key = (orig_fmt, dest_fmt, paso_fmt, eq)
        if key not in corridor_groups:
            corridor_groups[key] = {
                "origin": orig_fmt,
                "destination": dest_fmt,
                "border_crossing": paso_fmt,
                "equipment_type": eq,
                "origin_lat": co[0],
                "origin_lon": co[1],
                "dest_lat": cd[0],
                "dest_lon": cd[1],
                "sales": [],
                "categories": Counter(),
                "merchandises": Counter(),
            }
        grp = corridor_groups[key]
        grp["sales"].append(sale_usd)
        grp["categories"][cat] += 1
        grp["merchandises"][merc_str.title()] += 1

    wb.close()

    truck_labels = {
        "FRIO": "Furgón Refrigerado (Activo)",
        "IMO": "Semirremolque IMO (Activo)",
        "SECO": "Semirremolque Seco (Activo)",
    }

    tariffs: List[Dict[str, Any]] = []
    for grp in corridor_groups.values():
        med_sale = round(float(statistics.median(grp["sales"])), 2)
        eq = grp["equipment_type"]

        # Estimar costo fletero realista usando margen histórico del corredor si existe, o 85% (15% margen bruto)
        cost_ratio = 0.85
        if hist_routes and grp["origin_lat"] is not None and grp["dest_lat"] is not None:
            ratios = []
            for hr in hist_routes:
                if (hr.get("equipment_type") or "SECO") != eq:
                    continue
                hs = hr.get("sale_price_usd") or 0.0
                hc = hr.get("cost_price_usd") or 0.0
                if hs > 0 and 0 < hc < hs and hr.get("origin_lat") is not None and hr.get("dest_lat") is not None:
                    d_o = MatchingEngine.haversine_km(grp["origin_lat"], grp["origin_lon"], hr["origin_lat"], hr["origin_lon"])
                    d_d = MatchingEngine.haversine_km(grp["dest_lat"], grp["dest_lon"], hr["dest_lat"], hr["dest_lon"])
                    if d_o <= 60.0 and d_d <= 60.0:
                        ratios.append(hc / hs)
            if ratios:
                cost_ratio = min(0.89, max(0.78, float(statistics.median(ratios))))

        est_cost = round(med_sale * cost_ratio, 2)
        top_cat = grp["categories"].most_common(1)[0][0] if grp["categories"] else "Carga General"
        top_mercs = [m for m, _ in grp["merchandises"].most_common(2)]
        cat_label = top_cat if top_cat != "Otros" else (" / ".join(top_mercs) if top_mercs else "Carga General")

        tariffs.append({
            "company_id": 1,
            "origin": grp["origin"],
            "destination": grp["destination"],
            "border_crossing": grp["border_crossing"],
            "category": cat_label[:100],
            "truck_type": truck_labels.get(eq, "Semirremolque Seco (Activo)"),
            "equipment_type": eq,
            "sale_price_usd": med_sale,
            "estimated_carrier_cost_usd": est_cost,
            "is_active": True,
            "origin_lat": grp["origin_lat"],
            "origin_lon": grp["origin_lon"],
            "dest_lat": grp["dest_lat"],
            "dest_lon": grp["dest_lon"],
        })

    tariffs.sort(key=lambda t: (t["origin"], t["destination"], t["equipment_type"]))
    return {
        "active_clients": sorted(active_clients_set),
        "tariffs": tariffs,
        "client_routes": client_routes,
    }

