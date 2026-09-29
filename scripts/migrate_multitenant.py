"""
Migración Segura a Arquitectura Multi-Tenant crossTruck.
Ejecuta sentencias individuales compatibles con asyncpg.
"""
import asyncio
from sqlalchemy import text
from app.core.database import async_engine

STATEMENTS = [
    # 1. Enums
    """DO $$ BEGIN
        CREATE TYPE plantier AS ENUM ('TRIAL', 'STARTER', 'PRO', 'ENTERPRISE');
    EXCEPTION WHEN duplicate_object THEN null; END $$;""",

    """DO $$ BEGIN
        CREATE TYPE subscriptionstatus AS ENUM ('TRIAL', 'ACTIVE', 'PAUSED', 'CANCELLED');
    EXCEPTION WHEN duplicate_object THEN null; END $$;""",

    """DO $$ BEGIN
        CREATE TYPE trucktype AS ENUM ('SIDER', 'TERMICO', 'FURGON', 'BATEA', 'CHASIS', 'PLAYO', 'OTRO');
    EXCEPTION WHEN duplicate_object THEN null; END $$;""",

    """DO $$ BEGIN
        CREATE TYPE truckstatus AS ENUM ('DISPONIBLE', 'EN_VIAJE', 'EN_MANTENIMIENTO', 'INACTIVO');
    EXCEPTION WHEN duplicate_object THEN null; END $$;""",

    """DO $$ BEGIN
        CREATE TYPE demostatus AS ENUM ('NUEVO', 'CONTACTADO', 'DEMO_AGENDADA', 'CONVERTIDO', 'DESCARTADO');
    EXCEPTION WHEN duplicate_object THEN null; END $$;""",

    """DO $$ BEGIN
        ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'SUPERADMIN';
    EXCEPTION WHEN duplicate_object THEN null; END $$;""",

    # 2. Tabla companies
    """CREATE TABLE IF NOT EXISTS companies (
        id SERIAL PRIMARY KEY,
        name VARCHAR(200) NOT NULL,
        business_name VARCHAR(255),
        cuit_rut VARCHAR(50),
        country VARCHAR(100) DEFAULT 'Argentina' NOT NULL,
        contact_email VARCHAR(255),
        contact_phone VARCHAR(50),
        plan_tier plantier DEFAULT 'PRO' NOT NULL,
        subscription_status subscriptionstatus DEFAULT 'ACTIVE' NOT NULL,
        max_trucks INTEGER DEFAULT 50,
        max_users INTEGER DEFAULT 5,
        logo_url VARCHAR(500),
        notes TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );""",
    "CREATE INDEX IF NOT EXISTS ix_companies_name ON companies(name);",
    "CREATE INDEX IF NOT EXISTS ix_companies_cuit_rut ON companies(cuit_rut);",
    "CREATE INDEX IF NOT EXISTS ix_companies_is_active ON companies(is_active);",

    # 3. Tabla company_trucks
    """CREATE TABLE IF NOT EXISTS company_trucks (
        id SERIAL PRIMARY KEY,
        company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
        plate_number VARCHAR(50) NOT NULL,
        truck_type trucktype DEFAULT 'SIDER' NOT NULL,
        brand_model VARCHAR(150),
        model_year INTEGER,
        max_weight_kg FLOAT DEFAULT 28000.0,
        max_volume_m3 FLOAT DEFAULT 90.0,
        driver_name VARCHAR(150),
        driver_phone VARCHAR(50),
        status truckstatus DEFAULT 'DISPONIBLE' NOT NULL,
        current_city VARCHAR(150),
        notes TEXT,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );""",
    "CREATE INDEX IF NOT EXISTS ix_company_trucks_company_id ON company_trucks(company_id);",
    "CREATE INDEX IF NOT EXISTS ix_company_trucks_plate_number ON company_trucks(plate_number);",
    "CREATE INDEX IF NOT EXISTS ix_company_trucks_status ON company_trucks(status);",

    # 4. Tabla demo_requests
    """CREATE TABLE IF NOT EXISTS demo_requests (
        id SERIAL PRIMARY KEY,
        company_name VARCHAR(200) NOT NULL,
        contact_name VARCHAR(150) NOT NULL,
        email VARCHAR(255) NOT NULL,
        phone VARCHAR(50) NOT NULL,
        fleet_size VARCHAR(50),
        corridor_interest VARCHAR(200),
        notes TEXT,
        status demostatus DEFAULT 'NUEVO' NOT NULL,
        assigned_admin VARCHAR(150),
        created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );""",
    "CREATE INDEX IF NOT EXISTS ix_demo_requests_company_name ON demo_requests(company_name);",
    "CREATE INDEX IF NOT EXISTS ix_demo_requests_email ON demo_requests(email);",
    "CREATE INDEX IF NOT EXISTS ix_demo_requests_status ON demo_requests(status);",

    # 5. Agregar company_id a tablas existentes
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id) ON DELETE SET NULL;",
    "CREATE INDEX IF NOT EXISTS ix_users_company_id ON users(company_id);",
    "ALTER TABLE mercotruck_tariffs ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE;",
    "CREATE INDEX IF NOT EXISTS ix_mercotruck_tariffs_company_id ON mercotruck_tariffs(company_id);",
    "ALTER TABLE quote_history ADD COLUMN IF NOT EXISTS company_id INTEGER REFERENCES companies(id) ON DELETE CASCADE;",
    "CREATE INDEX IF NOT EXISTS ix_quote_history_company_id ON quote_history(company_id);"
]

async def migrate():
    print("🚀 Ejecutando migración multi-tenant para crossTruck...")
    # Paso 1: Enums y DDL
    async with async_engine.begin() as conn:
        for stmt in STATEMENTS:
            await conn.execute(text(stmt))
    print("✅ DDL y Enums aplicados y confirmados en PostgreSQL.")

    # Paso 2: DML (usando el nuevo enum SUPERADMIN en una nueva transacción)
    async with async_engine.begin() as conn:
        # Crear Tenant 1 Mercotruck si no existe
        res = await conn.execute(text("SELECT id FROM companies WHERE id = 1;"))
        if not res.fetchone():
            await conn.execute(text("""
                INSERT INTO companies (id, name, business_name, cuit_rut, country, contact_email, plan_tier, subscription_status, max_trucks, max_users, notes)
                VALUES (1, 'Mercotruck Logistics', 'Mercotruck S.R.L.', '30-71589423-9', 'Argentina', 'operaciones@mercotruck.com', 'PRO', 'ACTIVE', 50, 10, 'Cliente histórico inicial migrado a crossTruck');
            """))
            await conn.execute(text("SELECT setval('companies_id_seq', (SELECT MAX(id) FROM companies));"))
            print("✅ Empresa inicial Mercotruck Logistics (Tenant #1) creada.")

        # Asignar tarifas a tenant 1
        t_upd = await conn.execute(text("UPDATE mercotruck_tariffs SET company_id = 1 WHERE company_id IS NULL;"))
        print(f"✅ Tarifas vinculadas a Mercotruck: {t_upd.rowcount}")

        # Asignar cotizaciones a tenant 1
        q_upd = await conn.execute(text("UPDATE quote_history SET company_id = 1 WHERE company_id IS NULL;"))
        print(f"✅ Cotizaciones vinculadas a Mercotruck: {q_upd.rowcount}")

        # Actualizar superadmin
        await conn.execute(text("UPDATE users SET role = 'SUPERADMIN', company_id = NULL WHERE email = 'superadmin@mercotruck.com';"))
        print("✅ Usuario superadmin@mercotruck.com configurado como SUPERADMIN.")

        # Crear camiones de ejemplo para Mercotruck si no tiene
        truck_count = await conn.execute(text("SELECT count(*) FROM company_trucks WHERE company_id = 1;"))
        if truck_count.scalar() == 0:
            truck_inserts = [
                ("AF-204-TR", "SIDER", "Scania R450 6x2", 2022, "Carlos Méndez", "+54 9 261 455-8910", "Mendoza", "DISPONIBLE"),
                ("AG-912-LK", "TERMICO", "Volvo FH 540", 2023, "Jorge Peralta", "+54 9 11 3244-1190", "Buenos Aires", "EN_VIAJE"),
                ("AE-481-MN", "SIDER", "Mercedes-Benz Actros 2548", 2021, "Matías Rivas", "+54 9 261 512-3344", "Santiago de Chile", "DISPONIBLE"),
                ("AD-339-PX", "BATEA", "Iveco Stralis Hi-Way", 2020, "Roberto Gómez", "+54 9 341 688-9900", "Rosario", "DISPONIBLE")
            ]
            for plate, ttype, brand, year, driver, phone, city, status in truck_inserts:
                await conn.execute(text(f"""
                    INSERT INTO company_trucks (company_id, plate_number, truck_type, brand_model, model_year, driver_name, driver_phone, current_city, status)
                    VALUES (1, '{plate}', '{ttype}', '{brand}', {year}, '{driver}', '{phone}', '{city}', '{status}');
                """))
            print("✅ 4 unidades de flota inicial creadas para Mercotruck Logistics.")

    print("🎉 Migración Multi-Tenant crossTruck ejecutada con éxito!")

if __name__ == "__main__":
    asyncio.run(migrate())
