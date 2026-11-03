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
from app.domain.services.entity_linker import clean_company_name, clean_tax_id, infer_shipment_route
from app.domain.services.pricing_engine import PricingEngine
from app.etl.parsers.historico_parser import parse_historico_excel
from app.etl.parsers.softtrade_parser import parse_softtrade_impo, parse_softtrade_expo, categorizar_mercaderia

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

    with sync_engine.begin() as conn:
        migrations = [
            ("users", "company_id", "INTEGER REFERENCES companies(id) ON DELETE SET NULL"),
            ("mercotruck_tariffs", "company_id", "INTEGER REFERENCES companies(id) ON DELETE CASCADE"),
            ("mercotruck_tariffs", "equipment_type", "VARCHAR(30) DEFAULT 'SECO'"),
            ("quote_history", "company_id", "INTEGER REFERENCES companies(id) ON DELETE CASCADE"),
            ("mercotruck_routes", "unit_type", "VARCHAR(60)"),
            ("mercotruck_routes", "equipment_type", "VARCHAR(30) DEFAULT 'SECO'"),
            ("mercotruck_routes", "pack_type", "VARCHAR(60)"),
            ("mercotruck_routes", "is_imo", "VARCHAR(10)"),
            ("prospects", "trade_name", "VARCHAR(255)"),
            ("prospects", "equipment_type", "VARCHAR(30) DEFAULT 'SECO'"),
            ("prospects", "data_confidence", "VARCHAR(30) DEFAULT 'ALTA'"),
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
                conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN IF NOT EXISTS {col} {col_type}"))
            except Exception as e:
                logger.debug(f"Column {col} on {tbl} add skip: {e}")

    db = SyncSessionLocal()
    try:
        create_default_users(db)
    except Exception as e:
        logger.warning(f"No se pudo asegurar usuarios por defecto: {e}")
    finally:
        db.close()


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

    master_admin = db.query(User).filter(User.email.in_(["superadmin@mercotruck.com", "superadmin@crosstruck.com"])).first()
    if not master_admin:
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
    else:
        master_admin.email = "superadmin@mercotruck.com"
        master_admin.role = UserRole.SUPERADMIN
        master_admin.full_name = "Soporte Técnico Mercotruck Radar"
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

        # Indexamos tanto por CUSTOMER (importador/consignee en Chile) como por CLIENTE (dador comercial)
        for entity_raw in (customer_raw, client_raw):
            norm_k = clean_company_name(entity_raw)
            if not norm_k or len(norm_k) < 3:
                continue
            bucket = grouped[norm_k]
            bucket["legal_names"][entity_raw] += 1
            if client_raw and clean_company_name(client_raw) != norm_k:
                bucket["trade_names"][client_raw] += 1
            elif client_raw:
                bucket["trade_names"][client_raw] += 1
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
    clear_existing: bool = True,
):
    """Ejecuta el pipeline ETL de alta precisión (90%-95%) cargando los excels en PostgreSQL."""
    init_db_tables()
    db = SyncSessionLocal()

    try:
        create_default_users(db)

        if clear_existing:
            logger.info("Limpiando despachos, prospectos y rutas previas (preservando ClientMasterProfile verificado)...")
            db.execute(delete(SofttradeShipment))
            db.execute(delete(Prospect))
            db.execute(delete(MercotruckRoute))
            db.execute(delete(MercotruckTariff))
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
                data_dict = {
                    "origin": r.get("origin"),
                    "destination": r.get("destination"),
                    "shipper": r.get("shipper_name") or r.get("client_name"),
                    "customer": r.get("customer_name") or r.get("client_name"),
                    "trade_name": r.get("client_name"),
                    "equipment_type": r.get("equipment_type", "SECO"),
                }
                if client_c and len(client_c) > 2:
                    historic_entity_map[client_c] = data_dict
                if customer_c and len(customer_c) > 2:
                    historic_entity_map[customer_c] = data_dict

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
            tariff_objs = []
            for t_data in tariff_map.values():
                sales = t_data["sales"]
                costs = t_data["costs"]
                med_sale = round(float(statistics.median(sales)), 2) if sales else 2500.0
                med_cost = round(float(statistics.median(costs)), 2) if costs else round(med_sale * 0.82, 2)
                eq = t_data["equipment_type"]

                tariff_objs.append(MercotruckTariff(
                    company_id=1,
                    origin=t_data["origin"],
                    destination=t_data["destination"],
                    border_crossing=t_data["border_crossing"],
                    category=t_data["category"],
                    truck_type=truck_labels.get(eq, "Semirremolque Seco"),
                    equipment_type=eq,
                    sale_price_usd=med_sale,
                    estimated_carrier_cost_usd=med_cost,
                    is_active=True,
                    origin_lat=t_data["origin_lat"],
                    origin_lon=t_data["origin_lon"],
                    dest_lat=t_data["dest_lat"],
                    dest_lon=t_data["dest_lon"],
                ))

            db.bulk_save_objects(tariff_objs)
            db.commit()
            logger.info(f"Tarifario Maestro Propio poblado con {len(tariff_objs)} tarifas por equipo (mediana).")

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

        logger.info(f"Insertando {len(prospects_map)} prospectos FTL depurados en PostgreSQL...")
        for _, p_data in prospects_map.items():
            shipments_data = p_data.pop("shipments")
            eq_counter = p_data.pop("_eq_counter")
            cat_counter = p_data.pop("_cat_counter")

            p_data["equipment_type"] = eq_counter.most_common(1)[0][0] if eq_counter else "SECO"
            if cat_counter:
                p_data["primary_category"] = cat_counter.most_common(1)[0][0]

            # Mediana FTL reciente ponderada por camión como Flete Real de Mercado
            robust_price = PricingEngine.compute_robust_market_price(shipments_data)
            if robust_price <= 0:
                tc = p_data["total_trucks"]
                tf = p_data["total_freight_usd"]
                robust_price = round(tf / tc, 2) if tc > 0 else 0.0

            p_data["avg_freight_per_truck_usd"] = robust_price
            p_data["status"] = ProspectStatus.PROSPECT

            prospect_obj = Prospect(**p_data)
            db.add(prospect_obj)
            db.flush()

            shipment_objs = []
            for s_dict in shipments_data:
                s_dict["prospect_id"] = prospect_obj.id
                shipment_objs.append(SofttradeShipment(**s_dict))

            db.bulk_save_objects(shipment_objs)

        db.commit()

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
