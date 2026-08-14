import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Dict, Any, Tuple
from app.domain.services.geo_service import resolver_origen_impo, get_coords
from app.domain.services.pricing_engine import PricingEngine

MERC_CATEGORIAS = [
    ('Carnes y derivados',    ['CARNE','VACUNO','BOVINO','PORCINO','POLLO','CERDO','CORDERO','FRIGORIF','EMBUTIDO','SALCHICHA','JAMON','FIAMBRE','VISCERA','MONDONGO']),
    ('Frutas y verduras',     ['PALTA','LIMON','UVA','CEREZA','KIWI','ARANDANO','MANZANA','PERA','DURAZNO','CITRICO','FRUTA','VERDURA','TOMATE','PAPA','CEBOLLA','AJO','LECHUGA','ESPINACA','ZAPALLO','BROCOLI','FRAMBUESA']),
    ('Alimentos mascotas',    ['ALIMENTO PARA PERRO','ALIMENTO PARA GATO','ALIMENTO PARA MASCOTA','ALIMENTOS PARA PERRO','ALIMENTOS PARA GATO','ALIMENTOS PARA MASCOTA','ALIMENTOS PARA ANIMALE','PET FOOD','COMIDA PARA PERRO','COMIDA PARA GATO']),
    ('Aceites y grasas',      ['ACEITE','GRASA','ACIDO GRASO','OLEINA','SEBO','MARGARINA','MANTECA']),
    ('Azúcar y dulces',       ['AZUCAR','GLUCOSA','FRUCTOSA','JARABE','CARAMELO','CHOCOLATE','CACAO','DULCE','MIEL','ALMÍBAR','GALLETITA','GALLETA','BIZCOCHO','ALFAJOR']),
    ('Cereales y harinas',    ['MAIZ','TRIGO','SOJA','ARROZ','HARINA','ALMIDON','FÉCULA','CEREAL','GRANOLA','AVENA','CEBADA','SORGO','GIRASOL','MANI','EXPELLER','PELLET','SEMILLA']),
    ('Lácteos',               ['QUESO','LECHE','YOGUR','MANTEQUILLA','MANTECA','CREMA','SUERO','LACTEO','LACTOSUERO']),
    ('Bebidas',               ['VINO','CERVEZA','BEBIDA','JUGO','NECTAR','GASEOSA','AGUA MINERAL','SPIRITS','WHISKY','LICOR','SIDRA']),
    ('Tabaco',                ['CIGARRILLO','TABACO','CIGARRO']),
    ('Pasta y panificados',   ['PASTA','FIDEOS','SPAGHETTI','PASTA ALIMENTICIA','PANIFICADO','PAN','TOSTADA']),
    ('Congelados y helados',  ['HELADO','CONGELADO','PRECOCINADO','PAPAS PREFRITA','PAPAS PREPARA','PIZZA','EMPANADA']),
    ('Yerba y infusiones',    ['YERBA','MATE','TE ','CAFE','INFUSION','HIERBA']),
    ('Químicos industriales', ['ACIDO','SOLVENTE','RESINA','PIGMENTO','TINTA','BARNIZ','PINTURA','DISOLVENTE','BREA','ADITIVO','ANHIDRIDO','REACTIVO','CATALIZADOR','BIOCIDA','FUNGICIDA','HERBICIDA','PESTICIDA']),
    ('Plásticos y polímeros', ['POLIPROPILENO','POLIETILENO','POLIESTIRENO','PVC','PLASTICO','RESINA PLASTICA','POLIMERO','GRANULO']),
    ('Metales y siderurgia',  ['ACERO','HIERRO','ALUMINIO','COBRE','ZINC','PLOMO','ALAMBRE','ALAMBRON','CHAPA','PLANCHA','TUBO','CAÑO','PERFIL METALICO','BARRA DE','LINGOTE']),
    ('Papel y cartón',        ['PAPEL','CARTON','CARTULINA','CAJA DE CARTON','ENVASE DE CARTON','BOLSA DE PAPEL','TISSUE','HIGIENICO']),
    ('Vidrio y cerámica',     ['VIDRIO','CERAMICA','PORCELANA','LADRILL','BALDOSA','REVESTIMIENTO']),
    ('Madera y corcho',       ['MADERA','TAPON DE CORCHO','CORCHO','MADERA ASERRADA','TRIPLAY','MDF']),
    ('Combustibles y gas',    ['GAS PROPANO','GAS BUTANO','CARBON VEGETAL','CARBON','GLP','GNL','COMBUSTIBLE','GASOIL','NAFTA','KEROSENE','COQUE']),
    ('Textil y calzado',      ['TELA','TEJIDO','CALCETINE','MEDIA ','ROPA','INDUMENTARIA','CALZADO','ZAPATO','BOTA','CAMISA','PANTALON','VESTIDO','TEXTIL','HILO','LANA ','FIBRA TEXTIL']),
    ('Envases y embalajes',   ['ENVASE','BOTELLA','LATA ','TARRO','TAMBOR','BIDON','SACHET','BANDEJA','BOLSA','CONTENEDOR','EMBALAJE']),
    ('Vehículos y autopartes',['CAMIONETA','STATION WAGON','AUTOMOVIL','VEHICULO','AUTOPARTE','REPUESTO','NEUMATICO','LLANTA','MOTOR AUTOMOTRIZ']),
    ('Materiales construcción',['CEMENTO','CAL VIVA','YESO','ARENA','HORMIGON','AGREGADO','REVESTIMIENTO','AISLANTE','LANA DE VIDRIO','FIBRA DE VIDRIO']),
    ('Maquinaria y equipos',  ['MAQUINARIA','EQUIPO','MOTOR ','TURBINA','COMPRESOR','BOMBA ','VALVULA','ELECTRODOMESTICO','CALEFACTOR','GENERADOR']),
    ('Electrónica',           ['ELECTRONICO','ELECTRONICA','CABLES','INTERRUPTOR','PILAS','BATERIA','TRANSFORMADOR','CIRCUITO']),
    ('Farmacia y salud',      ['FARMACO','MEDICAMENTO','CAPSULAS','AMPOLLA','COMPRIMIDO','VACUNA','ANTIBIOTICO','VITAMINA','SUPLEMENTO','COSMETICO','PERFUME','SHAMPOO','JABÓN','DETERGENTE','LIMPIEZA']),
    ('Alimentación animal',   ['HARINA DE PESCADO','ALIMENTO PARA AVES','ALIMENTO PARA PECES','ALIMENTO GANADO','SILO','FORRAJE','BALANCEADO']),
    ('Minerales y fertilizantes',['UREA','FERTILIZANTE','MINERAL','SULFATO','FOSFATO','NITRATO','POTASIO','AZUFRE','SAL INDUSTRIAL']),
    ('Salmon y pesca',        ['SALMON','TRUCHA','MERLUZA','PESCADO','MARISCO','CALAMAR','ATUN','FILETE DE']),
]

def categorizar_mercaderia(nombre: str) -> str:
    if not nombre or str(nombre).strip().lower() in ('nan', 'none', '', 'no disponible'):
        return 'Otros'
    n = str(nombre).upper().strip()
    for cat, keywords in MERC_CATEGORIAS:
        if any(kw in n for kw in keywords):
            return cat
    return 'Otros'

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
            "category": cat,
        })
    return shipments
