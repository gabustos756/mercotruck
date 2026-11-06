import os
import logging
import statistics
from collections import Counter, defaultdict
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import delete, text

from app.core.database import sync_engine, SyncSessionLocal, Base
from app.domain.models.user import User, UserRole
from app.domain.models.prospect import Prospect, ProspectStatus, ProspectFuente
from app.domain.models.shipment import SofttradeShipment
from app.domain.models.route import MercotruckRoute
from app.domain.models.tariff import MercotruckTariff
from app.domain.models.client_master_profile import ClientMasterProfile
from app.domain.models.prospect_geo_intel import ProspectGeoIntel
from app.domain.models.company import Company
from app.domain.models.truck import CompanyTruck
from app.domain.models.demo_request import DemoRequest
from app.domain.services.entity_linker import clean_company_name, clean_tax_id, infer_shipment_route, is_chilean_city
from app.domain.services.pricing_engine import PricingEngine
from app.etl.parsers.historico_parser import parse_historico_excel
from app.etl.parsers.softtrade_parser import parse_softtrade_impo, parse_softtrade_expo, categorizar_mercaderia
from app.etl.parsers.tarifario_activo_parser import (
    DEFAULT_TARIFARIO_ACTIVO_PATH,
    get_active_client_matcher,
    parse_tarifario_activo_excel,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ETLPipeline")


def init_db_tables():
    """Crea y migra sin pérdida la estructura de tablas en PostgreSQL."""
    logger.info("Creando y verificando tablas relacionales en PostgreSQL...")
    try:
        with sync_engine.begin() as conn:
            conn.execute(text("DO $$ BEGIN ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SUPERADMIN'; EXCEPTION WHEN duplicate_object THEN null; END $$;"))
    except Exception as e:
        logger.debug(f"Enum SUPERADMIN add check: {e}")

    Base.metadata.create_all(bind=sync_engine)

    migrations = [
        ("users", "company_id", "INTEGER REFERENCES companies(id) ON DELETE SET NULL"),
        ("mercotruck_tariffs", "company_id", "INTEGER REFERENCES companies(id) ON DELETE CASCADE"),
        ("mercotruck_tariffs", "equipment_type", "VARCHAR(30) DEFAULT 'SECO'"),
        ("mercotruck_tariffs", "tariff_source", "VARCHAR(40) DEFAULT 'HISTORICO_AUTO'"),
        ("quote_history", "company_id", "INTEGER REFERENCES companies(id) ON DELETE CASCADE"),
        ("mercotruck_routes", "unit_type", "VARCHAR(60)"),
        ("mercotruck_routes", "equipment_type", "VARCHAR(30) DEFAULT 'SECO'"),
        ("mercotruck_routes", "pack_type", "VARCHAR(60)"),
        ("mercotruck_routes", "is_imo", "VARCHAR(10)"),
        ("prospects", "trade_name", "VARCHAR(255)"),
        ("prospects", "equipment_type", "VARCHAR(30) DEFAULT 'SECO'"),
        ("prospects", "data_confidence", "VARCHAR(30) DEFAULT 'ALTA'"),
        ("prospects", "is_existing_client", "BOOLEAN DEFAULT FALSE"),
        ("prospects", "active_client_alias", "VARCHAR(150)"),
        ("softtrade_shipments", "real_origin_city", "VARCHAR(150)"),
        ("softtrade_shipments", "real_destination_city", "VARCHAR(150)"),
        ("softtrade_shipments", "customs_office_code", "VARCHAR(100)"),
        ("softtrade_shipments", "shipper_name", "VARCHAR(255)"),
        ("softtrade_shipments", "consignee_name", "VARCHAR(255)"),
        ("softtrade_shipments", "geo_inference_level", "VARCHAR(50)"),
        ("softtrade_shipments", "product_clean", "VARCHAR(200)"),
        ("softtrade_shipments", "bultos_count", "INTEGER DEFAULT 0"),
        ("softtrade_shipments", "raw_freight_per_truck_usd", "FLOAT DEFAULT 0.0"),
        ("softtrade_shipments", "estimated_real_freight_per_truck_usd", "FLOAT DEFAULT 0.0"),
        ("softtrade_shipments", "incoterm", "VARCHAR(30)"),
        ("softtrade_shipments", "equipment_type", "VARCHAR(30) DEFAULT 'SECO'"),
        ("softtrade_shipments", "stowage_type", "VARCHAR(100)"),
    ]
    for tbl, col, col_type in migrations:
        try:
            with sync_engine.begin() as conn:
                conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {col_type}"))
        except Exception as e:
            logger.debug(f"Column {col} on {tbl} add skip: {e}")

    db = SyncSessionLocal()
    try:
        create_default_users(db)
        if os.path.exists(DEFAULT_TARIFARIO_ACTIVO_PATH):
            sync_active_tariffs_and_clients(db, DEFAULT_TARIFARIO_ACTIVO_PATH)
    except Exception as e:
        db.rollback()
        logger.warning(f"No se pudo asegurar usuarios/tarifario activo por defecto: {e}")
    finally:
        db.close()


def sync_active_tariffs_and_clients(
    db: Session,
    tarifario_path: str = DEFAULT_TARIFARIO_ACTIVO_PATH,
    hist_routes: List[Dict[str, Any]] = None,
) -> Dict[str, int]:
    """
    Sincroniza de forma idempotente (sin pérdida de tarifas MANUALES):
      1. El Tarifario Maestro (MercotruckTariff) desde 'Tarifario Activo Octubre - Actualidad.xlsx' (Prioridad #1).
      2. La marca is_existing_client / active_client_alias en Prospect para evitar pisar clientes vigentes.
    """
    if not os.path.exists(tarifario_path):
        return {"tariffs_synced": 0, "clients_flagged": 0}

    if hist_routes is None:
        db_routes = db.query(MercotruckRoute).all()
        hist_routes = [
            {
                "equipment_type": r.equipment_type or "SECO",
                "sale_price_usd": r.sale_price_usd,
                "cost_price_usd": r.cost_price_usd,
                "origin_lat": r.origin_lat,
                "origin_lon": r.origin_lon,
                "dest_lat": r.dest_lat,
                "dest_lon": r.dest_lon,
            }
            for r in db_routes
        ]

    parsed = parse_tarifario_activo_excel(tarifario_path, hist_routes=hist_routes)
    active_tariffs = parsed["tariffs"]

    existing_all = db.query(MercotruckTariff).all()
    manual_keys = set()
    auto_by_key: Dict[tuple, MercotruckTariff] = {}

    for t in existing_all:
        src = (getattr(t, "tariff_source", None) or "HISTORICO_AUTO").upper()
        key = (
            (t.origin or "").strip().upper(),
            (t.destination or "").strip().upper(),
            (t.border_crossing or "").strip().upper(),
            (t.equipment_type or "SECO").strip().upper(),
        )
        if src == "MANUAL":
            manual_keys.add(key)
        else:
            if key in auto_by_key:
                db.delete(t)
            else:
                auto_by_key[key] = t

    seen_active_keys = set()
    synced_count = 0
    for td in active_tariffs:
        key = (
            td["origin"].strip().upper(),
            td["destination"].strip().upper(),
            (td["border_crossing"] or "").strip().upper(),
            (td["equipment_type"] or "SECO").strip().upper(),
        )
        seen_active_keys.add(key)
        if key in manual_keys:
            continue

        existing_t = auto_by_key.get(key)
        if existing_t:
            existing_t.company_id = 1
            existing_t.origin = td["origin"]
            existing_t.destination = td["destination"]
            existing_t.border_crossing = td["border_crossing"]
            existing_t.category = td["category"]
            existing_t.truck_type = td["truck_type"]
            existing_t.equipment_type = td["equipment_type"]
            existing_t.tariff_source = "TARIFARIO_ACTIVO"
            existing_t.sale_price_usd = td["sale_price_usd"]
            existing_t.estimated_carrier_cost_usd = td["estimated_carrier_cost_usd"]
            existing_t.is_active = True
            existing_t.origin_lat = td["origin_lat"]
            existing_t.origin_lon = td["origin_lon"]
            existing_t.dest_lat = td["dest_lat"]
            existing_t.dest_lon = td["dest_lon"]
        else:
            db.add(MercotruckTariff(
                tariff_source="TARIFARIO_ACTIVO",
                **td,
            ))
        synced_count += 1

    # Eliminar tarifas automáticas viejas (HISTORICO_AUTO) que ya no pertenecen al Tarifario Activo oficial
    for key, old_t in auto_by_key.items():
        if key not in seen_active_keys:
            db.delete(old_t)

    # Marcar clientes vigentes de Mercotruck en la tabla de Prospectos
    matcher = get_active_client_matcher(tarifario_path)
    shipper_by_prospect = {}
    for pid, sh in (
        db.query(SofttradeShipment.prospect_id, SofttradeShipment.shipper_name)
        .filter(SofttradeShipment.shipper_name.isnot(None))
        .distinct()
        .all()
    ):
        if sh and sh != "EXPORTADOR NO DECLARADO":
            shipper_by_prospect.setdefault(pid, sh)

    flagged_count = 0
    for p in db.query(Prospect).all():
        hit = matcher.match_entity(p.name, p.trade_name, shipper_by_prospect.get(p.id))
        is_cli = bool(hit)
        if p.is_existing_client != is_cli or p.active_client_alias != hit:
            p.is_existing_client = is_cli
            p.active_client_alias = hit
        if is_cli:
            flagged_count += 1

    db.commit()
    try:
        from app.web.controllers.dashboard_controller import clear_evaluated_prospects_cache
        clear_evaluated_prospects_cache()
    except Exception:
        pass

    logger.info(
        f"✅ Tarifario Activo Octubre-Actualidad sincronizado: {synced_count} tarifas activas vigentes | "
        f"{flagged_count} cuentas marcadas como clientes actuales Mercotruck."
    )
    return {"tariffs_synced": synced_count, "clients_flagged": flagged_count}


def recategorize_existing_shipments(db: Session) -> int:
    """Actualiza product_clean y re-categoriza los envíos existentes en la base de datos."""
    from app.domain.services.merchandise_service import clean_product_name, categorizar_mercaderia

    shipments = db.query(SofttradeShipment).all()
    if not shipments:
        return 0

    updated_count = 0
    for s in shipments:
        raw = s.merchandise_desc or ""
        new_clean = clean_product_name(raw)
        new_cat = categorizar_mercaderia(raw)

        if s.product_clean != new_clean or s.category != new_cat:
            s.product_clean = new_clean
            s.category = new_cat
            updated_count += 1

    db.commit()
    logger.info(f"Re-categorizados y normalizados {updated_count} envíos en softtrade_shipments.")
    return updated_count


def create_default_users(db: Session):
    """Inicializa las cuentas corporativas de Mercotruck Radar (incluyendo Matías Palomino)."""
    from app.core.security import get_password_hash
    from app.domain.models.company import Company, PlanTier, SubscriptionStatus

    target_pwd = "ggsolutions123"
    pwd_hash = get_password_hash(target_pwd)
    matias_pwd_hash = get_password_hash("Mercotruck2026!")

    tenant1 = db.query(Company).filter(Company.id == 1).first()
    if not tenant1:
        tenant1 = Company(
            id=1,
            name="Mercotruck Logistics",
            business_name="Mercotruck S.R.L.",
            cuit_rut="30-71589423-9",
            country="Argentina",
            contact_email="mpalomino@mercotruck.com",
            plan_tier=PlanTier.PRO,
            subscription_status=SubscriptionStatus.ACTIVE,
            max_trucks=50,
            max_users=10,
        )
        db.add(tenant1)
        db.commit()

    merco_sa = db.query(User).filter(User.email == "superadmin@mercotruck.com").first()
    legacy_sa = db.query(User).filter(User.email == "superadmin@crosstruck.com").first()

    if merco_sa:
        merco_sa.role = UserRole.SUPERADMIN
        merco_sa.full_name = "Soporte Técnico Mercotruck Radar"
        merco_sa.company_id = 1
        merco_sa.is_active = True
        if legacy_sa:
            # Si coexisten ambas cuentas en PostgreSQL, desactivamos la legacy sin renombrar email
            # para no violar ix_users_email ni romper llaves foráneas históricas.
            legacy_sa.is_active = False
        db.commit()
    elif legacy_sa:
        legacy_sa.email = "superadmin@mercotruck.com"
        legacy_sa.role = UserRole.SUPERADMIN
        legacy_sa.full_name = "Soporte Técnico Mercotruck Radar"
        legacy_sa.company_id = 1
        legacy_sa.is_active = True
        db.commit()
    else:
        master_admin = User(
            email="superadmin@mercotruck.com",
            full_name="Soporte Técnico Mercotruck Radar",
            hashed_password=pwd_hash,
            role=UserRole.SUPERADMIN,
            company_id=1,
            is_active=True,
        )
        db.add(master_admin)
        db.commit()

    legacy_client = db.query(User).filter(User.email == "admin@crosstruck.com").first()
    if legacy_client:
        legacy_client.is_active = False
        db.commit()

    client_admin = db.query(User).filter(User.email == "admin@mercotruck.com").first()
    if not client_admin:
        client_admin = User(
            email="admin@mercotruck.com",
            full_name="Administrador Mercotruck",
            hashed_password=pwd_hash,
            role=UserRole.ADMIN,
            company_id=1,
            is_active=True,
        )
        db.add(client_admin)
        db.commit()

    matias_user = db.query(User).filter(User.email == "mpalomino@mercotruck.com").first()
    if not matias_user:
        matias_user = User(
            email="mpalomino@mercotruck.com",
            full_name="Matías Palomino",
            hashed_password=matias_pwd_hash,
            role=UserRole.ADMIN,
            company_id=1,
            is_active=True,
        )
        db.add(matias_user)
        db.commit()
        logger.info("✅ Cuenta directiva inicializada: mpalomino@mercotruck.com")
    else:
        matias_user.full_name = "Matías Palomino"
        matias_user.role = UserRole.ADMIN
        matias_user.company_id = 1
        matias_user.is_active = True
        db.commit()


def seed_master_profiles_from_historico(db: Session, hist_routes: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    Siembra o actualiza ClientMasterProfile desde HISTORICO_MERCOTRUCK.xlsx vinculando:
    CUSTOMER / CLIENTE <-> Nombre de Fantasía (CLIENTE) <-> SHIPPER <-> Planta Origen / Destino <-> Equipo,
    respetando SIEMPRE intactos los perfiles marcados con is_human_verified == True (Mesa de los Lunes).
    """
    existing_profiles = db.query(ClientMasterProfile).all()
    existing_by_key = {p.normalized_key: p for p in existing_profiles}

    grouped = defaultdict(lambda: {
        "legal_names": Counter(),
        "trade_names": Counter(),
        "shippers": Counter(),
        "origins": Counter(),
        "destinations": Counter(),
        "equipments": Counter(),
        "packs": Counter(),
    })

    for r in hist_routes:
        client_raw = (r.get("client_name") or "").strip()
        customer_raw = (r.get("customer_name") or "").strip()
        shipper_raw = (r.get("shipper_name") or "").strip()
        orig = (r.get("origin") or "").strip()
        dest = (r.get("destination") or "").strip()
        eq = (r.get("equipment_type") or "SECO").strip().upper()
        pack = (r.get("pack_type") or "").strip().upper()

        r_dir = "EXPO" if is_chilean_city(orig) else "IMPO"
        # Indexamos por (entidad, sentido IMPO/EXPO) para no mezclar rutas Arg->Chile con retornos Chile->Arg
        for entity_raw in (customer_raw, client_raw):
            base_k = clean_company_name(entity_raw)
            if not base_k or len(base_k) < 3:
                continue
            norm_k = f"{base_k}:{r_dir}"
            bucket = grouped[norm_k]
            bucket["legal_names"][entity_raw] += 1
            if client_raw and clean_company_name(client_raw) != base_k:
                bucket["trade_names"][client_raw] += 1
            elif shipper_raw and clean_company_name(shipper_raw) != base_k:
                bucket["trade_names"][shipper_raw] += 1
            if shipper_raw:
                bucket["shippers"][shipper_raw] += 1
            if orig:
                bucket["origins"][orig] += 1
            if dest:
                bucket["destinations"][dest] += 1
            bucket["equipments"][eq] += 1
            if pack:
                bucket["packs"][pack] += 1

    upserted = 0
    for norm_k, data in grouped.items():
        existing = existing_by_key.get(norm_k)
        if existing and existing.is_human_verified:
            continue

        legal_best = data["legal_names"].most_common(1)[0][0]
        trade_best = data["trade_names"].most_common(1)[0][0] if data["trade_names"] else None
        shipper_best = data["shippers"].most_common(1)[0][0] if data["shippers"] else None
        orig_best = data["origins"].most_common(1)[0][0] if data["origins"] else None
        dest_best = data["destinations"].most_common(1)[0][0] if data["destinations"] else None
        eq_best = data["equipments"].most_common(1)[0][0] if data["equipments"] else "SECO"

        if existing:
            existing.legal_name = legal_best
            existing.trade_name = trade_best
            existing.shipper_plant_name = shipper_best
            existing.verified_origin_city = orig_best
            existing.verified_dest_city = dest_best
            existing.default_equipment = eq_best
        else:
            new_prof = ClientMasterProfile(
                normalized_key=norm_k,
                legal_name=legal_best,
                trade_name=trade_best,
                shipper_plant_name=shipper_best,
                verified_origin_city=orig_best,
                verified_dest_city=dest_best,
                default_equipment=eq_best,
                pallet_mode="AUTO",
                is_human_verified=False,
            )
            db.add(new_prof)
            existing_by_key[norm_k] = new_prof
        upserted += 1

    db.commit()
    logger.info(f"Padrón Fijo ClientMasterProfile sincronizado: {upserted} perfiles automáticos ({len(existing_by_key)} totales).")

    # Construir mapa rápido en memoria (por normalized_key y por RUT:<clean_rut>)
    master_map: Dict[str, Dict[str, Any]] = {}
    for prof in db.query(ClientMasterProfile).all():
        d = {
            "id": prof.id,
            "normalized_key": prof.normalized_key,
            "tax_id": prof.tax_id,
            "legal_name": prof.legal_name,
            "trade_name": prof.trade_name,
            "shipper_plant_name": prof.shipper_plant_name,
            "verified_origin_city": prof.verified_origin_city,
            "verified_dest_city": prof.verified_dest_city,
            "default_equipment": prof.default_equipment,
            "pallet_mode": prof.pallet_mode,
            "is_human_verified": prof.is_human_verified,
            "notes": prof.notes,
        }
        master_map[prof.normalized_key] = d
        clean_r = clean_tax_id(prof.tax_id or "")
        if clean_r:
            master_map[f"RUT:{clean_r}"] = d
    return master_map


def run_etl_pipeline(
    historico_path: str = "docs/HISTORICO_MERCOTRUCK.xlsx",
    impo_path: str = "docs/SOFTTRADE_IMPO.xlsx",
    expo_path: str = "docs/SOFTTRADE_EXPO.xlsx",
    tarifario_activo_path: str = DEFAULT_TARIFARIO_ACTIVO_PATH,
    clear_existing: bool = True,
):
    """Ejecuta el pipeline ETL de alta precisión (90%-95%) cargando los excels en PostgreSQL."""
    init_db_tables()
    db = SyncSessionLocal()

    try:
        create_default_users(db)

        if clear_existing:
            logger.info("Actualizando despachos y rutas base (preservando IDs de Prospectos, CRM, Contactos, Tarifas editadas y Padrón Fijo)...")
            db.execute(delete(SofttradeShipment))
            db.execute(delete(MercotruckRoute))
            db.commit()

        hist_routes: List[Dict[str, Any]] = []
        historic_entity_map: Dict[str, Dict[str, Any]] = {}

        # 1. Cargar Histórico Mercotruck, Sembrar Padrón Fijo & Poblar Tarifario por Equipo
        if os.path.exists(historico_path):
            logger.info(f"Procesando {historico_path} (excluyendo TRUCKY y separando SECO/FRIO/IMO)...")
            hist_routes = parse_historico_excel(historico_path)
            logger.info(f"Insertando {len(hist_routes)} rutas históricas de semirremolques Mercotruck...")

            route_objs = [MercotruckRoute(**r) for r in hist_routes]
            db.bulk_save_objects(route_objs)
            db.commit()

            for r in hist_routes:
                client_c = clean_company_name(r.get("client_name") or "")
                customer_c = clean_company_name(r.get("customer_name") or "")
                r_dir = "EXPO" if is_chilean_city(r.get("origin") or "") else "IMPO"
                data_dict = {
                    "origin": r.get("origin"),
                    "destination": r.get("destination"),
                    "shipper": r.get("shipper_name") or r.get("client_name"),
                    "customer": r.get("customer_name") or r.get("client_name"),
                    "trade_name": r.get("client_name"),
                    "equipment_type": r.get("equipment_type", "SECO"),
                }
                if client_c and len(client_c) > 2:
                    historic_entity_map[f"{client_c}:{r_dir}"] = data_dict
                    historic_entity_map.setdefault(client_c, data_dict)
                if customer_c and len(customer_c) > 2:
                    historic_entity_map[f"{customer_c}:{r_dir}"] = data_dict
                    historic_entity_map.setdefault(customer_c, data_dict)

            if os.path.exists(tarifario_activo_path):
                sync_active_tariffs_and_clients(db, tarifario_activo_path, hist_routes=hist_routes)
            else:
                tariff_map = {}
                for r in hist_routes:
                    orig = r["origin"]
                    dest = r["destination"]
                    paso = r.get("border_crossing") or "LIBERTADORES"
                    cat = categorizar_mercaderia(r.get("merchandise"))
                    eq = r.get("equipment_type") or "SECO"
                    key = (orig, dest, paso, cat, eq)

                    if key not in tariff_map:
                        tariff_map[key] = {
                            "origin": orig,
                            "destination": dest,
                            "border_crossing": paso,
                            "category": cat,
                            "equipment_type": eq,
                            "sales": [],
                            "costs": [],
                            "origin_lat": r.get("origin_lat"),
                            "origin_lon": r.get("origin_lon"),
                            "dest_lat": r.get("dest_lat"),
                            "dest_lon": r.get("dest_lon"),
                        }

                    if r.get("sale_price_usd") and r["sale_price_usd"] > 0:
                        tariff_map[key]["sales"].append(r["sale_price_usd"])
                    if r.get("cost_price_usd") and r["cost_price_usd"] > 0:
                        tariff_map[key]["costs"].append(r["cost_price_usd"])

                truck_labels = {
                    "FRIO": "Furgón Refrigerado",
                    "IMO": "Semirremolque IMO",
                    "SECO": "Semirremolque Seco",
                }
                existing_tariff_keys = {
                    (
                        (t.origin or "").strip().upper(),
                        (t.destination or "").strip().upper(),
                        (t.border_crossing or "").strip().upper(),
                        (t.category or "").strip().upper(),
                        (t.equipment_type or "SECO").strip().upper(),
                    )
                    for t in db.query(MercotruckTariff).all()
                }

                tariff_objs = []
                for t_data in tariff_map.values():
                    sales = t_data["sales"]
                    costs = t_data["costs"]
                    med_sale = round(float(statistics.median(sales)), 2) if sales else 2500.0
                    med_cost = round(float(statistics.median(costs)), 2) if costs else round(med_sale * 0.82, 2)
                    eq = t_data["equipment_type"]
                    t_key = (
                        (t_data["origin"] or "").strip().upper(),
                        (t_data["destination"] or "").strip().upper(),
                        (t_data["border_crossing"] or "").strip().upper(),
                        (t_data["category"] or "").strip().upper(),
                        (eq or "SECO").strip().upper(),
                    )
                    if t_key in existing_tariff_keys:
                        continue

                    tariff_objs.append(MercotruckTariff(
                        company_id=1,
                        origin=t_data["origin"],
                        destination=t_data["destination"],
                        border_crossing=t_data["border_crossing"],
                        category=t_data["category"],
                        truck_type=truck_labels.get(eq, "Semirremolque Seco"),
                        equipment_type=eq,
                        tariff_source="HISTORICO_AUTO",
                        sale_price_usd=med_sale,
                        estimated_carrier_cost_usd=med_cost,
                        is_active=True,
                        origin_lat=t_data["origin_lat"],
                        origin_lon=t_data["origin_lon"],
                        dest_lat=t_data["dest_lat"],
                        dest_lon=t_data["dest_lon"],
                    ))

                if tariff_objs:
                    db.bulk_save_objects(tariff_objs)
                    db.commit()
                logger.info(f"Tarifario Maestro sincronizado ({len(tariff_objs)} nuevas tarifas agregadas, {len(existing_tariff_keys)} preservadas).")

        master_profile_map = seed_master_profiles_from_historico(db, hist_routes)

        # 2. Cargar Manifiestos FTL IMPO & EXPO (sin LTL, con rescate multi-camión)
        all_shipments = []
        seen_doc_keys = set()

        def add_shipments_dedup(shipments_list: List[Dict[str, Any]], source_label: str):
            added_count = 0
            for s in shipments_list:
                doc_key = (
                    s.get("fuente"),
                    str(s.get("document_id") or "").strip().upper(),
                    str(s.get("prospect_name") or "").strip().upper(),
                )
                if doc_key not in seen_doc_keys:
                    seen_doc_keys.add(doc_key)
                    all_shipments.append(s)
                    added_count += 1
            logger.info(f"[{source_label}] Extraídos {len(shipments_list)} CRTs/DUAs FTL ({added_count} nuevos únicos).")

        if os.path.exists(impo_path):
            logger.info(f"Procesando sábana base IMPO: {impo_path}...")
            add_shipments_dedup(parse_softtrade_impo(impo_path), "IMPO Base")

        if os.path.exists(expo_path):
            logger.info(f"Procesando sábana base EXPO: {expo_path}...")
            add_shipments_dedup(parse_softtrade_expo(expo_path), "EXPO Base")

        softrade_folder = os.path.join(os.path.dirname(impo_path), "softrade")
        if os.path.exists(softrade_folder):
            import glob
            softrade_files = sorted(glob.glob(os.path.join(softrade_folder, "*.xlsx")))
            logger.info(f"Encontrados {len(softrade_files)} archivos bimestrales en {softrade_folder}...")
            for fpath in softrade_files:
                fname = os.path.basename(fpath).upper()
                if "~$" in fname:
                    continue
                if "ARG - CHILE" in fname or "IMPO" in fname:
                    add_shipments_dedup(parse_softtrade_impo(fpath), f"IMPO {fname}")
                elif "CHILE - ARG" in fname or "EXPO" in fname:
                    add_shipments_dedup(parse_softtrade_expo(fpath), f"EXPO {fname}")

        # 3. Enriquecer cada despacho con el Motor de 5 Niveles y agrupar por Prospecto
        logger.info(f"Enriqueciendo y agrupando prospectos FTL (Total CRTs/DUAs únicos: {len(all_shipments)})...")
        prospects_map = {}

        for s in all_shipments:
            p_name = s.pop("prospect_name")
            p_tax_id = s.pop("prospect_tax_id")
            fuente = s["fuente"]

            infer_res = infer_shipment_route(
                {
                    "fuente": fuente,
                    "prospect_name": p_name,
                    "prospect_tax_id": p_tax_id,
                    "origin_str": s.get("origin_str"),
                    "destination_str": s.get("destination_str"),
                    "border_crossing": s.get("border_crossing"),
                    "category": s.get("category"),
                    "merchandise_desc": s.get("merchandise_desc"),
                    "document_id": s.get("document_id"),
                    "freight_per_truck_usd": s.get("estimated_real_freight_per_truck_usd") or s.get("freight_per_truck_usd"),
                },
                historic_entity_map=historic_entity_map,
                routes_cache=hist_routes,
                master_profile_map=master_profile_map,
            )

            # Si el perfil maestro fijó un modo de pallets específico (Mesa de los Lunes), recalcular camiones
            p_mode = infer_res.get("pallet_mode") or "AUTO"
            if p_mode != "AUTO":
                re_eval = PricingEngine.evaluate_ftl_shipment(
                    gross_weight_kg=s["gross_weight_kg"],
                    bultos=s.get("bultos_count", 0),
                    freight_total_usd=s["freight_usd"],
                    fuente=fuente,
                    pallet_mode=p_mode,
                )
                if re_eval["is_ftl"] and re_eval["trucks_count"] > 0:
                    s["trucks_count"] = re_eval["trucks_count"]
                    s["raw_freight_per_truck_usd"] = re_eval["raw_freight_per_truck_usd"]
                    real_cam = PricingEngine.calibrate_real_freight_usd(
                        raw_freight_per_truck_usd=re_eval["raw_freight_per_truck_usd"],
                        incoterm=s.get("incoterm") or "",
                        origin_str=infer_res["real_origin_city"],
                        fuente=fuente,
                    )
                    s["estimated_real_freight_per_truck_usd"] = real_cam
                    s["freight_per_truck_usd"] = real_cam
                    s["stowage_type"] = re_eval["stowage_type"]

            if infer_res.get("override_equipment"):
                s["equipment_type"] = infer_res["override_equipment"]

            s["real_origin_city"] = infer_res["real_origin_city"]
            s["real_destination_city"] = infer_res["real_destination_city"]
            s["customs_office_code"] = infer_res["customs_office_code"]
            s["shipper_name"] = infer_res["shipper_name"]
            s["consignee_name"] = infer_res["consignee_name"]
            s["geo_inference_level"] = infer_res["geo_inference_level"]

            key = (p_name.upper(), fuente)
            if key not in prospects_map:
                prospects_map[key] = {
                    "name": p_name,
                    "trade_name": infer_res.get("trade_name"),
                    "tax_id": p_tax_id,
                    "fuente": ProspectFuente.IMPO if fuente == "IMPO" else ProspectFuente.EXPO,
                    "primary_category": s["category"],
                    "data_confidence": infer_res.get("data_confidence", "ALTA"),
                    "total_shipments": 0,
                    "total_trucks": 0,
                    "total_freight_usd": 0.0,
                    "last_shipment_date": None,
                    "_eq_counter": Counter(),
                    "_cat_counter": Counter(),
                    "shipments": [],
                }

            pm = prospects_map[key]
            if not pm["tax_id"] and p_tax_id:
                pm["tax_id"] = p_tax_id
            if not pm["trade_name"] and infer_res.get("trade_name"):
                pm["trade_name"] = infer_res["trade_name"]
            pm["total_shipments"] += 1
            pm["total_trucks"] += s["trucks_count"]
            pm["total_freight_usd"] += s["freight_usd"]
            pm["_eq_counter"][s["equipment_type"]] += s["trucks_count"]
            pm["_cat_counter"][s["category"]] += s["trucks_count"]

            s_date = s["shipment_date"]
            if s_date:
                if pm["last_shipment_date"] is None or s_date > pm["last_shipment_date"]:
                    pm["last_shipment_date"] = s_date

            pm["shipments"].append(s)

        logger.info(f"Sincronizando {len(prospects_map)} prospectos FTL depurados en PostgreSQL (Upsert sin pérdida de CRM)...")
        existing_prospects = db.query(Prospect).all()
        existing_by_key = {}
        for ep in existing_prospects:
            ep_fuente = ep.fuente.value if hasattr(ep.fuente, "value") else str(ep.fuente)
            existing_by_key[((ep.name or "").strip().upper(), ep_fuente)] = ep

        seen_prospect_ids = set()
        all_shipment_objs = []

        for (p_key_name, p_key_fuente), p_data in prospects_map.items():
            shipments_data = p_data.pop("shipments")
            eq_counter = p_data.pop("_eq_counter")
            cat_counter = p_data.pop("_cat_counter")

            p_data["equipment_type"] = eq_counter.most_common(1)[0][0] if eq_counter else "SECO"
            if cat_counter:
                p_data["primary_category"] = cat_counter.most_common(1)[0][0]

            # Mediana FTL reciente del Corredor Principal Operativo del cliente (manzanas con manzanas)
            corridor_info = PricingEngine.select_primary_corridor_and_price(shipments_data)
            robust_price = corridor_info["corridor_median_usd"]
            if robust_price <= 0:
                tc = p_data["total_trucks"]
                tf = p_data["total_freight_usd"]
                robust_price = round(tf / tc, 2) if tc > 0 else 0.0

            p_data["avg_freight_per_truck_usd"] = robust_price

            prospect_obj = existing_by_key.get((p_key_name, p_key_fuente))
            if prospect_obj:
                # Actualizar métricas preservando ID, status del CRM, comercial asignado, notas y relaciones
                prospect_obj.trade_name = p_data.get("trade_name") or prospect_obj.trade_name
                prospect_obj.tax_id = p_data.get("tax_id") or prospect_obj.tax_id
                prospect_obj.primary_category = p_data["primary_category"]
                prospect_obj.equipment_type = p_data["equipment_type"]
                prospect_obj.data_confidence = p_data["data_confidence"]
                prospect_obj.total_shipments = p_data["total_shipments"]
                prospect_obj.total_trucks = p_data["total_trucks"]
                prospect_obj.total_freight_usd = p_data["total_freight_usd"]
                prospect_obj.avg_freight_per_truck_usd = p_data["avg_freight_per_truck_usd"]
                prospect_obj.last_shipment_date = p_data["last_shipment_date"]
            else:
                p_data["status"] = ProspectStatus.PROSPECT
                prospect_obj = Prospect(**p_data)
                db.add(prospect_obj)
                db.flush()

            seen_prospect_ids.add(prospect_obj.id)

            for s_dict in shipments_data:
                s_dict["prospect_id"] = prospect_obj.id
                all_shipment_objs.append(SofttradeShipment(**s_dict))

        # Limpiar únicamente prospectos obsoletos sin actividad FTL y sin gestión comercial asociada
        from app.domain.models.quote_history import QuoteHistory
        protected_ids = {r[0] for r in db.query(QuoteHistory.prospect_id).distinct().all() if r[0]}
        for ep in existing_prospects:
            if ep.id not in seen_prospect_ids and ep.id not in protected_ids:
                if ep.status == ProspectStatus.PROSPECT and not ep.contacts and not ep.interactions and not ep.simulations:
                    db.delete(ep)

        db.bulk_save_objects(all_shipment_objs)
        db.commit()

        if os.path.exists(tarifario_activo_path):
            sync_active_tariffs_and_clients(db, tarifario_activo_path, hist_routes=hist_routes)

        try:
            from app.web.controllers.dashboard_controller import clear_evaluated_prospects_cache
            clear_evaluated_prospects_cache()
        except Exception:
            pass

        logger.info("✅ ETL Pipeline de Alta Precisión completado exitosamente.")

    except Exception as e:
        db.rollback()
        logger.error(f"Error en ETL Pipeline: {e}", exc_info=True)
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    run_etl_pipeline()
