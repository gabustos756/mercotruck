import os
import logging
from datetime import datetime
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import delete

from app.core.database import sync_engine, SyncSessionLocal, Base
from app.domain.models.user import User, UserRole
from app.domain.models.prospect import Prospect, ProspectStatus, ProspectFuente
from app.domain.models.shipment import SofttradeShipment
from app.domain.models.route import MercotruckRoute
from app.domain.models.tariff import MercotruckTariff
from app.domain.models.prospect_geo_intel import ProspectGeoIntel
from app.etl.parsers.historico_parser import parse_historico_excel
from app.etl.parsers.softtrade_parser import parse_softtrade_impo, parse_softtrade_expo, categorizar_mercaderia

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ETLPipeline")

from sqlalchemy import text

def init_db_tables():
    """Crea la estructura de tablas en la base de datos si no existen."""
    logger.info("Creando tablas relacionales en PostgreSQL...")
    Base.metadata.create_all(bind=sync_engine)
    
    with sync_engine.begin() as conn:
        for col, col_type in [
            ("real_origin_city", "VARCHAR(150)"),
            ("real_destination_city", "VARCHAR(150)"),
            ("customs_office_code", "VARCHAR(100)"),
            ("shipper_name", "VARCHAR(255)"),
            ("consignee_name", "VARCHAR(255)"),
            ("geo_inference_level", "VARCHAR(50)"),
            ("product_clean", "VARCHAR(200)")
        ]:
            try:
                conn.execute(text(f"ALTER TABLE softtrade_shipments ADD COLUMN IF NOT EXISTS {col} {col_type}"))
            except Exception as e:
                logger.debug(f"Column {col} add skip: {e}")

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
    """Crea usuario admin y usuarios comerciales por defecto si no existen."""
    if not db.query(User).filter(User.email == "admin@mercotruck.com").first():
        admin = User(
            email="admin@mercotruck.com",
            full_name="Administrador Mercotruck",
            hashed_password="adminpassword123", # In production use bcrypt hash
            role=UserRole.ADMIN,
            is_active=True
        )
        db.add(admin)
        logger.info("Usuario Admin creado: admin@mercotruck.com")
        
    if not db.query(User).filter(User.email == "dino@mercotruck.com").first():
        comm1 = User(
            email="dino@mercotruck.com",
            full_name="Dino Commercial",
            hashed_password="password123",
            role=UserRole.COMMERCIAL,
            is_active=True
        )
        db.add(comm1)
        
    if not db.query(User).filter(User.email == "martin@mercotruck.com").first():
        comm2 = User(
            email="martin@mercotruck.com",
            full_name="Martin Commercial",
            hashed_password="password123",
            role=UserRole.COMMERCIAL,
            is_active=True
        )
        db.add(comm2)
        
    db.commit()

def run_etl_pipeline(
    historico_path: str = "docs/HISTORICO_MERCOTRUCK.xlsx",
    impo_path: str = "docs/SOFTTRADE_IMPO.xlsx",
    expo_path: str = "docs/SOFTTRADE_EXPO.xlsx",
    clear_existing: bool = True
):
    """Ejecuta el pipeline ETL completo cargando los excels en PostgreSQL."""
    init_db_tables()
    db = SyncSessionLocal()
    
    try:
        create_default_users(db)
        
        if clear_existing:
            logger.info("Limpiando datos anteriores en PostgreSQL...")
            db.execute(delete(SofttradeShipment))
            db.execute(delete(Prospect))
            db.execute(delete(MercotruckRoute))
            db.execute(delete(MercotruckTariff))
            db.commit()

        # 1. Cargar Histórico Mercotruck & Poblar Tarifario Propio Maestro
        if os.path.exists(historico_path):
            logger.info(f"Procesando {historico_path}...")
            hist_routes = parse_historico_excel(historico_path)
            logger.info(f"Insertando {len(hist_routes)} rutas históricas de Mercotruck...")
            
            route_objs = [MercotruckRoute(**r) for r in hist_routes]
            db.bulk_save_objects(route_objs)
            db.commit()
            logger.info("Rutas históricas insertadas con éxito.")

            # Agrupar cotizaciones e histórico para poblar el Tarifario Propio Maestro
            logger.info("Poblando Tarifario Maestro Propio desde el histórico de cotizaciones Mercotruck...")
            tariff_map = {} # (origin, destination, border) -> {sales: [], costs: [], lat/lons}
            
            for r in hist_routes:
                orig = r["origin"]
                dest = r["destination"]
                paso = r.get("border_crossing") or "LIBERTADORES"
                cat = categorizar_mercaderia(r.get("merchandise"))
                key = (orig, dest, paso, cat)
                
                if key not in tariff_map:
                    tariff_map[key] = {
                        "origin": orig,
                        "destination": dest,
                        "border_crossing": paso,
                        "category": cat,
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

            tariff_objs = []
            for t_data in tariff_map.values():
                sales = t_data["sales"]
                costs = t_data["costs"]
                
                avg_sale = round(sum(sales) / len(sales), 2) if sales else 2500.0
                avg_cost = round(sum(costs) / len(costs), 2) if costs else round(avg_sale * 0.8, 2)
                
                tariff_objs.append(MercotruckTariff(
                    origin=t_data["origin"],
                    destination=t_data["destination"],
                    border_crossing=t_data["border_crossing"],
                    category=t_data["category"],
                    truck_type="General",
                    sale_price_usd=avg_sale,
                    estimated_carrier_cost_usd=avg_cost,
                    is_active=True,
                    origin_lat=t_data["origin_lat"],
                    origin_lon=t_data["origin_lon"],
                    dest_lat=t_data["dest_lat"],
                    dest_lon=t_data["dest_lon"]
                ))
                
            db.bulk_save_objects(tariff_objs)
            db.commit()
            logger.info(f"Tarifario Maestro Propio poblado con {len(tariff_objs)} tarifas clave desde HISTORICO_MERCOTRUCK.")

        # 2. Cargar Softtrade IMPO & EXPO (Sábanas históricas + Archivos bimestrales en docs/softrade/)
        all_shipments = []
        seen_doc_keys = set() # (fuente, document_id, item, prospect_name)

        def add_shipments_dedup(shipments_list: List[Dict[str, Any]], source_label: str):
            added_count = 0
            for s in shipments_list:
                doc_key = (
                    s.get("fuente"),
                    str(s.get("document_id") or "").strip().upper(),
                    str(s.get("item") or "").strip(),
                    str(s.get("prospect_name") or "").strip().upper()
                )
                if doc_key not in seen_doc_keys:
                    seen_doc_keys.add(doc_key)
                    all_shipments.append(s)
                    added_count += 1
            logger.info(f"[{source_label}] Extraídos {len(shipments_list)} envíos ({added_count} nuevos únicos).")

        # 2a. Sábanas base si existen
        if os.path.exists(impo_path):
            logger.info(f"Procesando sábana base IMPO: {impo_path}...")
            add_shipments_dedup(parse_softtrade_impo(impo_path), "IMPO Base")

        if os.path.exists(expo_path):
            logger.info(f"Procesando sábana base EXPO: {expo_path}...")
            add_shipments_dedup(parse_softtrade_expo(expo_path), "EXPO Base")

        # 2b. Archivos bimestrales en docs/softrade/
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
                    logger.info(f"Procesando archivo IMPO (Arg -> Chile): {fname}...")
                    parsed = parse_softtrade_impo(fpath)
                    add_shipments_dedup(parsed, f"IMPO {fname}")
                elif "CHILE - ARG" in fname or "EXPO" in fname:
                    logger.info(f"Procesando archivo EXPO (Chile -> Arg): {fname}...")
                    parsed = parse_softtrade_expo(fpath)
                    add_shipments_dedup(parsed, f"EXPO {fname}")

        # 3. Agrupar Prospectos y Cargar Envíos en Postgres/SQLite
        logger.info(f"Agrupando y cargando prospectos y envíos (Total únicos: {len(all_shipments)})...")
        
        prospects_map = {} # (name_upper, fuente) -> dict
        
        for s in all_shipments:
            p_name = s.pop("prospect_name")
            p_tax_id = s.pop("prospect_tax_id")
            fuente = s["fuente"]
            key = (p_name.upper(), fuente)
            
            if key not in prospects_map:
                prospects_map[key] = {
                    "name": p_name,
                    "tax_id": p_tax_id,
                    "fuente": ProspectFuente.IMPO if fuente == "IMPO" else ProspectFuente.EXPO,
                    "primary_category": s["category"],
                    "total_shipments": 0,
                    "total_trucks": 0,
                    "total_freight_usd": 0.0,
                    "last_shipment_date": None,
                    "shipments": []
                }
                
            pm = prospects_map[key]
            pm["total_shipments"] += 1
            pm["total_trucks"] += s["trucks_count"]
            pm["total_freight_usd"] += s["freight_usd"]
            
            s_date = s["shipment_date"]
            if s_date:
                if pm["last_shipment_date"] is None or s_date > pm["last_shipment_date"]:
                    pm["last_shipment_date"] = s_date
                    
            pm["shipments"].append(s)

        # Batch insert prospectos y sus envíos
        logger.info(f"Insertando {len(prospects_map)} prospectos únicos en la Base de Datos...")
        
        for p_key, p_data in prospects_map.items():
            shipments_data = p_data.pop("shipments")
            
            tc = p_data["total_trucks"]
            tf = p_data["total_freight_usd"]
            p_data["avg_freight_per_truck_usd"] = round(tf / tc, 2) if tc > 0 else 0.0
            p_data["status"] = ProspectStatus.PROSPECT
            
            prospect_obj = Prospect(**p_data)
            db.add(prospect_obj)
            db.flush() # obtiene prospect_obj.id
            
            shipment_objs = []
            for s_dict in shipments_data:
                s_dict["prospect_id"] = prospect_obj.id
                shipment_objs.append(SofttradeShipment(**s_dict))
                
            db.bulk_save_objects(shipment_objs)
            
        db.commit()
        
        # Invalidar memoria caché del Dashboard si está importada
        try:
            from app.web.controllers.dashboard_controller import _EVALUATED_PROSPECTS_CACHE
            _EVALUATED_PROSPECTS_CACHE.clear()
        except Exception:
            pass

        logger.info("ETL Pipeline completado exitosamente.")
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error en ETL Pipeline: {e}", exc_info=True)
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    run_etl_pipeline()
