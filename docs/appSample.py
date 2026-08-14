"""
Mercotruck — Buscador de Clientes Potenciales  v5.3
=====================================================
Cambios v5.3:
  - Columna Diferencia % separada de Mercotruck (ordenable independientemente)
  - Filtro de categoría como desplegable (select) en lugar de texto libre
  - Endpoint /api/categorias para cargar opciones dinámicamente
  - Scoring EXACTO/CERCANO más preciso (radio 50km EXACTO, 100km CERCANO)
  - "OTROS ARGENTINA" resuelto por código de aduana del documento (primeros 3 dígitos)
  - Estados (contactado/descartado) eliminados — simplificación para v1
  - Paginado en desglose de documentos (10 por página)
  - Categorización de mercaderías (30 categorías agrupadas)
  - Sort por score de oportunidad: camiones × competitividad de precio
  - Cálculo de camiones corregido: siempre techo 28.500 kg (sin distinción por bultos)
  - Ícono "+" en lugar del teléfono para ver ficha
"""

import os, io, csv, warnings
from datetime import datetime, date, timedelta
from flask import Flask, render_template_string, jsonify, request, Response
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')
app = Flask(__name__)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
DATA_FOLDER = r"C:\Users\Gabriel Salgado\OneDrive - Ecipsa\Grabaciones\Escritorio\Personal\Agentes\Mercotruck\Datos"
HIST_FILE   = os.path.join(DATA_FOLDER, "HISTORICO_MERCOTRUCK.xlsx")
IMPO_FILE   = os.path.join(DATA_FOLDER, "SOFTTRADE_IMPO.xlsx")
EXPO_FILE   = os.path.join(DATA_FOLDER, "SOFTTRADE_EXPO.xlsx")

FLETE_MIN     = 500
FLETE_MAX     = 8000
DOCS_MIN      = 5
RADIO_EXACTO  = 50     # km para EXACTO (antes 100)
RADIO_CERCANO = 100    # km para CERCANO
DIAS_RECIENTE = 90

# ── ENGINE ────────────────────────────────────────────────────────────────────
def _engine():
    try:
        import python_calamine; return 'calamine'
    except ImportError:
        return 'openpyxl'

# ── ADUANAS ARGENTINAS ────────────────────────────────────────────────────────
ADUANAS = {
    '001':('Bs.As. Capital',      (-34.603,-58.381)),
    '003':('Bahía Blanca',         (-38.719,-62.270)),
    '004':('Bahía Blanca',         (-38.719,-62.270)),
    '005':('Barranqueras',         (-27.484,-58.941)),
    '006':('Bs.As. Palermo',       (-34.588,-58.416)),
    '007':('Campana',              (-34.163,-58.959)),
    '008':('Campana',              (-34.163,-58.959)),
    '009':('Clorinda',             (-25.283,-57.722)),
    '010':('Comodoro Rivadavia',   (-45.864,-67.500)),
    '011':('Concordia',            (-31.393,-58.021)),
    '012':('Córdoba',              (-31.417,-64.183)),
    '013':('Corrientes',           (-27.467,-58.833)),
    '014':('Cruz Alta',            (-33.013,-61.814)),
    '016':('Mendoza',              (-32.890,-68.845)),
    '017':('Córdoba',              (-31.417,-64.183)),
    '018':('Reconquista',          (-29.144,-59.646)),
    '019':('Resistencia',          (-27.451,-58.986)),
    '020':('Diamante',             (-32.074,-60.638)),
    '023':('Esquel',               (-42.909,-71.320)),
    '024':('Formosa',              (-26.180,-58.175)),
    '025':('Goya',                 (-29.141,-59.263)),
    '026':('Gualeguaychú',         (-33.011,-58.518)),
    '029':('Iguazú',               (-25.588,-54.566)),
    '031':('Jujuy',                (-24.185,-65.299)),
    '033':('La Plata',             (-34.921,-57.954)),
    '034':('La Quiaca',            (-22.103,-65.598)),
    '037':('Mar del Plata',        (-38.005,-57.541)),
    '038':('Mendoza',              (-32.890,-68.845)),
    '040':('Necochea',             (-38.554,-58.739)),
    '041':('Paraná',               (-31.733,-60.530)),
    '042':('Paso de los Libres',   (-29.718,-57.090)),
    '045':('Pocitos',              (-22.383,-63.692)),
    '046':('Posadas',              (-27.367,-55.896)),
    '047':('Pto. Madryn',          (-42.768,-65.038)),
    '048':('Río Gallegos',         (-51.623,-69.216)),
    '049':('Río Grande',           (-53.788,-67.707)),
    '052':('Rosario',              (-32.946,-60.639)),
    '053':('Salta',                (-24.783,-65.423)),
    '054':('San Javier',           (-30.576,-59.944)),
    '055':('San Juan',             (-31.537,-68.536)),
    '057':('San Lorenzo',          (-32.744,-60.737)),
    '059':('San Nicolás',          (-33.336,-60.209)),
    '060':('San Pedro',            (-33.679,-59.666)),
    '062':('Santa Fe',             (-31.620,-60.699)),
    '066':('Tinogasta',            (-28.066,-67.567)),
    '067':('Ushuaia',              (-54.801,-68.302)),
    '069':('Villa Constitución',   (-33.227,-60.337)),
    '073':('Ezeiza',               (-34.822,-58.535)),
    '074':('Tucumán',              (-26.808,-65.218)),
    '075':('Neuquén',              (-38.952,-68.059)),
    '076':('Orán',                 (-23.135,-64.325)),
    '078':('San Rafael',           (-34.617,-68.330)),
    '079':('La Rioja',             (-29.413,-66.855)),
    '080':('San Antonio Oeste',    (-40.731,-65.011)),
    '082':('Bernardo de Irigoyen', (-26.291,-53.650)),
    '083':('San Luis',             (-33.295,-66.338)),
    '084':('Santo Tomé',           (-28.546,-56.043)),
    '085':('Villa Regina',         (-39.101,-67.075)),
    '086':('Oberá',                (-27.487,-55.119)),
    '087':('Caleta Olivia',        (-46.440,-67.526)),
    '088':('General Deheza',       (-33.765,-63.787)),
    '089':('Santiago del Estero',  (-27.794,-64.261)),
    '090':('General Pico',         (-35.656,-63.757)),
    '091':('Bs.As. Norte',         (-34.520,-58.479)),
    '092':('Bs.As. Sur',           (-34.700,-58.400)),
    '099':('Multiaduana',          (-34.603,-58.381)),
}

# ── COORDENADAS ───────────────────────────────────────────────────────────────
COORDS = {
    'OTROS ARGENTINA':(-34.603,-58.381),'BUENOS AIRES':(-34.603,-58.381),
    'MENDOZA':(-32.890,-68.845),'CORDOBA':(-31.417,-64.183),
    'ROSARIO':(-32.946,-60.639),'BAHIA BLANCA':(-38.719,-62.270),
    'MAR DEL PLATA':(-38.005,-57.541),'COMODORO RIVADAVIA':(-45.864,-67.500),
    'TUCUMAN':(-26.808,-65.218),'SALTA':(-24.783,-65.423),
    'NEUQUEN':(-38.952,-68.059),'SANTA FE':(-31.620,-60.699),
    'POSADAS':(-27.367,-55.896),'CORRIENTES':(-27.467,-58.833),
    'JUJUY':(-24.185,-65.299),'SAN FRANCISCO':(-31.425,-62.084),
    'TUCUMAN - COLOMBRES':(-26.578,-64.936),
    'SALTA - TABACAL':(-23.246,-64.262),'SALTA - METAN VIEJO':(-25.498,-64.970),
    'SALTA - MOSCONI':(-22.614,-63.812),'SALTA - PICHANAL':(-23.322,-64.218),
    'SALTA - ROSARIO DE LA FRONTERA':(-25.803,-64.970),
    'SALTA - CERRILLOS':(-24.906,-65.486),'SALTA - CAMPO QUIJANO':(-24.909,-65.638),
    'SALTA - LAS LAJITAS':(-24.716,-63.481),'SALTA - CARBONCITO':(-22.860,-64.164),
    'JUJUY - PAMPA BLANCA':(-23.748,-65.397),
    'CORRIENTES - MERCEDES':(-29.182,-58.078),
    'CORRIENTES - PASO DE LOS LIBRES':(-29.718,-57.090),
    'MISIONES':(-27.367,-55.896),'MISIONES - SANTO PIPO':(-27.091,-55.431),
    'MISIONES - APOSTOLES':(-27.918,-55.758),'MISIONES - SANTA ANA':(-27.368,-55.577),
    'ENTRE RIOS':(-31.733,-60.530),'ENTRE RIOS - VILLA ELISA':(-32.169,-58.397),
    'ENTRE RIOS - CONCEPCION DEL URUGUAY':(-32.482,-58.238),
    'ENTRE RIOS - SAN SALVADOR':(-31.619,-58.503),
    'ENTRE RIOS - GUALEGUAYCHU':(-33.011,-58.518),
    'ENTRE RIOS - CRESPO':(-32.028,-60.311),'ENTRE RIOS - CHAJARI':(-30.760,-57.980),
    'ENTRE RIOS - CONCORDIA':(-31.393,-58.021),'ENTRE RIOS - NOGOYÁ':(-32.394,-59.793),
    'ENTRE RIOS - PARANA':(-31.733,-60.530),
    'SANTA FE - ROSARIO':(-32.946,-60.639),'SANTA FE - SAN JERONIMO SUD':(-32.695,-60.943),
    'SANTA FE - FRANCK':(-31.583,-61.284),'SANTA FE - RAFAELA':(-31.252,-61.487),
    'SANTA FE - FRONTERA':(-31.069,-61.521),'SANTA FE - ESPERANZA':(-31.447,-60.931),
    'SANTA FE - BELLA ITALIA':(-29.551,-60.663),'SANTA FE - CORONDA':(-31.974,-60.921),
    'SANTA FE - RECREO':(-31.485,-60.735),'SANTA FE - CARCARAÑA':(-32.856,-61.153),
    'SANTE FE - AREQUITO':(-33.143,-61.465),
    'CORDOBA - GRAL DEHEZA':(-33.765,-63.787),'CORDOBA - PORTEÑA':(-30.872,-62.005),
    'CORDOBA - GRAL CABRERA':(-32.808,-63.878),'CORDOBA - EL TIO':(-30.363,-62.583),
    'CORDOBA - TIO PUJIO':(-32.309,-63.320),'CORDOBA - VILLA MARIA':(-32.407,-63.238),
    'CORDOBA - ALEJANDRO ROCA':(-33.358,-63.723),'CORDOBA - RIO CUARTO':(-33.131,-64.349),
    'CORDOBA - MONTE CRISTO':(-31.345,-63.945),'CORDOBA - MORTEROS':(-30.707,-62.000),
    'CORDOBA - SANTA ROSA DE CALAMUCHITA':(-32.069,-64.540),
    'CORDOBA - PILAR':(-31.682,-63.879),'CORDOBA - TANCACHA':(-32.239,-63.953),
    'CORDOBA - HERNANDO':(-32.426,-63.729),'CORDOBA - CHALACEA':(-30.964,-63.561),
    'CORDOBA - JUAREZ CELMAN':(-33.040,-63.430),'CORDOBA - TICINO':(-33.060,-62.890),
    'BUENOS AIRES - BARADERO':(-33.808,-59.510),'BUENOS AIRES - MAR DEL PLATA':(-38.005,-57.541),
    'BUENOS AIRES - EZEIZA':(-34.822,-58.535),'BUENOS AIRES - BUENOS AIRES':(-34.603,-58.381),
    'BUENOS AIRES - CHACABUCO':(-34.642,-60.474),'BUENOS AIRES - EL TALAR PACHECO':(-34.462,-58.641),
    'BUENOS AIRES - PILAR':(-34.459,-58.915),'BUENOS AIRES - LANUS':(-34.701,-58.394),
    'BUENOS AIRES - ZARATE':(-34.101,-59.028),'BUENOS AIRES - AVELLANEDA':(-34.665,-58.368),
    'BUENOS AIRES - ESCOBAR':(-34.346,-58.796),'BUENOS AIRES - 9 DE JULIO':(-35.444,-60.882),
    'BUENOS AIRES - TRES ARROYOS':(-38.376,-60.275),'BUENOS AIRES - SAN PEDRO':(-33.679,-59.666),
    'BUENOS AIRES - BERAZATEGUI':(-34.762,-58.211),'BUENOS AIRES - TORTUGUITAS':(-34.428,-58.748),
    'BUENOS AIRES - BURZACO':(-34.831,-58.391),'BUENOS AIRES - LINCOLN':(-34.865,-61.527),
    'BUENOS AIRES - CAMPANA':(-34.163,-58.959),'BUENOS AIRES - LA PLATA':(-34.921,-57.954),
    'BUENOS AIRES - LOS CARDALES':(-34.332,-59.115),'BUENOS AIRES - PEHUAJO':(-35.810,-61.893),
    'BUENOS AIRES - ENSENADA':(-34.866,-57.908),
    'MENDOZA - LUJAN DE CUYO':(-33.072,-68.878),'MENDOZA - SAN RAFAEL':(-34.617,-68.330),
    'MENDOZA - TUNUYAN':(-33.578,-69.020),'MENDOZA - GRAL ALVEAR':(-34.978,-67.715),
    'SAN LUIS':(-33.295,-66.338),'SAN LUIS - ARGENTINA':(-33.295,-66.338),
    'SAN JUAN':(-31.537,-68.536),'SAN JUAN - CHIMBAS':(-31.459,-68.551),
    'LA RIOJA':(-29.413,-66.855),'LA RIOJA - ANGUINAN':(-29.272,-67.812),
    'RIO NEGRO - VIEDMA':(-40.812,-62.997),'CATAMARCA':(-28.469,-65.779),
    # Chile — historial DESTINO + EXPO ORIGEN
    'CLP - SANTIAGO':(-33.459,-70.648),'CLP - RANCAGUA':(-34.170,-70.741),
    'CLP - PUNTA ARENAS':(-53.163,-70.917),'CLP - OSORNO':(-40.573,-73.136),
    'CLP - CODEGUA':(-34.032,-70.682),'CLP - PUERTO SAN ANTONIO':(-33.593,-71.621),
    'CLP - SAN ANTONIO':(-33.593,-71.621),'CLP - PLACILLA':(-34.088,-70.693),
    'CLP - VALPARAISO':(-33.047,-71.619),'CLP - MOLINA':(-35.114,-71.283),
    'CLP - ILLAPEL':(-31.638,-71.163),'CLP - CURICO':(-34.985,-71.239),
    'CLP - LOS ANGELES':(-37.470,-72.354),'CLP - TALCA':(-35.426,-71.655),
    'CLP - CONCON':(-32.926,-71.527),'CLP - LA CALERA':(-32.786,-71.196),
    'CLP - TALAGANTE':(-33.666,-70.929),'CLP - LAMPA':(-33.281,-70.879),
    'CLP - TALCAHUANO':(-36.724,-73.115),'CLP - OHHIGNS':(-34.170,-70.741),
    'CLP - SAN FERNANDO':(-34.586,-70.993),'CLP - MARCHIGUE':(-34.395,-71.530),
    'CLP - PAINE':(-33.812,-70.739),'CLP - MALLOA':(-34.451,-70.955),
    'CLP - QUILLOTA':(-32.878,-71.248),'CLP - CASABLANCA':(-33.320,-71.420),
    'LOS ANDES':(-32.833,-70.600),'TALCAHUANO':(-36.724,-73.115),
    'OSORNO':(-40.573,-73.136),'ANTOFAGASTA':(-23.650,-70.400),
    'PUNTA ARENAS':(-53.163,-70.917),'PUERTO MONTT':(-41.472,-72.936),
    'ARICA':(-18.478,-70.322),'IQUIQUE':(-20.213,-70.152),
    'COYHAIQUE':(-45.571,-72.066),'METROPOLITANA':(-33.459,-70.648),
    'PUERTO AYSEN':(-45.401,-72.698),
    'BRA - SAO PABLO':(-23.550,-46.633),'BRA - PORTO ALEGRE':(-30.033,-51.230),
    'BRA - RIO DE JANEIRO':(-22.906,-43.173),'BRA - CAXIAS DO SUL':(-29.168,-51.179),
    'UY - URUGUAY':(-32.522,-55.765),'UY - MONTEVIDEO':(-34.901,-56.165),
    'PY - PARAGUAY':(-23.442,-58.444),'PY - CAPITAN MIRANDA':(-27.201,-55.811),
}

# ── PASOS ─────────────────────────────────────────────────────────────────────
PASO_FRAGS = {
    'LIBERTADORES':       ['LIBERTADORES'],
    'PINO HACHADO':       ['PINO HACHADO'],
    'CARDENAL SAMORE':    ['CARDENAL SAMORE','SAMORE'],
    'JAMA':               ['JAMA'],
    'COYHAIQUE':          ['COYHAIQUE','HUEMULES'],
    'INTEGRACION AUSTRAL':['INTEGRACION AUSTRAL','MONTE AYMOND'],
    'ENCARNACION':        ['ENCARNACION'],
    'FOZ DE IGUAZU':      ['FOZ DE IGUAZU','IGUAZU'],
    'FRAY BENTOS':        ['FRAY BENTOS'],
    'URUGUAYANA':         ['URUGUAYANA'],
    'FALCON CLORINDA':    ['FALCON','CLORINDA'],
}

def pasos_coinciden(ph, ps):
    ph = str(ph).upper().strip(); ps = str(ps).upper().strip()
    if not ph or not ps or ph in ('NAN','') or ps in ('NAN',''): return False
    return any(f in ps or ps in f for f in PASO_FRAGS.get(ph,[ph]))

# ── CATEGORÍAS DE MERCADERÍA ──────────────────────────────────────────────────
# Mapeo de palabras clave → categoría. Se evalúa en orden, primera coincidencia gana.
MERC_CATEGORIAS = [
    ('Carnes y derivados',    ['CARNE','VACUNO','BOVINO','PORCINO','POLLO','CERDO','CORDERO','FRIGORIF','EMBUTIDO','SALCHICHA','JAMON','FIAMBRE','VISCERA','MONDONGO']),
    ('Frutas y verduras',     ['PALTA','LIMON','UVA','CEREZA','KIWI','ARANDANO','MANZANA','PERA','DURAZNO','CITRICO','FRUTA','VERDURA','TOMATE','PAPA','CEBOLLA','AJO','LECHUGA','ESPINACA','ZAPALLO','BROCOLI','FRAMBUESA']),
    ('Alimentos mascotas',    ['ALIMENTO PARA PERRO','ALIMENTO PARA GATO','ALIMENTO PARA MASCOTA','ALIMENTOS PARA PERRO','ALIMENTOS PARA GATO','ALIMENTOS PARA MASCOTA','ALIMENTOS PARA ANIMALE','PET FOOD','COMIDA PARA PERRO','COMIDA PARA GATO']),
    ('Aceites y grasas',      ['ACEITE','GRASA','ACIDO GRASO','OLEINA','SEBO','MARGARINA','MANTECA']),
    ('Azúcar y dulces',       ['AZUCAR','GLUCOSA','FRUCTOSA','JARABE','CARAMELO','CHOCOLATE','CACAO','DULCE','MIEL','ALMÍBAR','GALLETITA','GALLETA','BIZCOCHO','ALFAJOR']),
    ('Cereales y harinas',    ['MAIZ','TRIGO','SOJA','ARROZ','HARINA','ALMIDON','ALMIDON','FÉCULA','CEREAL','GRANOLA','AVENA','CEBADA','SORGO','GIRASOL','MANI','EXPELLER','PELLET','SEMILLA']),
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
    ('Otros',                 []),  # catch-all
]

def categorizar_mercaderia(nombre):
    if not nombre or str(nombre).strip().lower() in ('nan','none','','no disponible'):
        return 'Sin clasificar'
    n = str(nombre).upper().strip()
    for cat, keywords in MERC_CATEGORIAS:
        if any(kw in n for kw in keywords):
            return cat
    return 'Otros'

# ── CACHÉ ─────────────────────────────────────────────────────────────────────
_cache = {
    'prospectos': None, 'rutas': None,
    'categorias': [], 'transportistas': [],
    'error': None, 'loaded_at': None,
}

# ── UTILIDADES ────────────────────────────────────────────────────────────────
_INVALIDOS = {'','nan','none','no disponible','no determinado','nd','n/d','sin datos','sin nombre'}

def get_coords(texto):
    if not texto or str(texto).strip() in ('','nan','NaT','No disponible','None'):
        return (None, None)
    t = str(texto).upper().strip()
    if t in COORDS: return COORDS[t]
    for k, v in COORDS.items():
        if k in t or t in k: return v
    return (None, None)

def get_coords_aduana(cod3):
    e = ADUANAS.get(str(cod3).zfill(3))
    return e[1] if e else None

def aduana_label(cod3):
    e = ADUANAS.get(str(cod3).zfill(3))
    return f"{cod3} - {e[0]}" if e else f"??? - {cod3}"

def resolver_origen_impo(puerto_embarque, doc_transporte):
    """
    Si Puerto de Embarque es 'OTROS ARGENTINA', resuelve por código de aduana
    del Documento de Transporte (primeros 3 caracteres).
    """
    if not puerto_embarque or str(puerto_embarque).upper().strip() in ('OTROS ARGENTINA',''):
        cod3 = str(doc_transporte).strip()[:3]
        coords = get_coords_aduana(cod3)
        label  = aduana_label(cod3)
        return label, coords
    return str(puerto_embarque).strip(), get_coords(str(puerto_embarque).strip())

def parsear_venta(v):
    try: return float(str(v).replace('$','').replace(',','').strip())
    except: return 0.0

def haversine_matrix(la1, lo1, la2, lo2):
    R = 6371.0
    la1 = np.radians(np.asarray(la1,float))[:,None]
    lo1 = np.radians(np.asarray(lo1,float))[:,None]
    la2 = np.radians(np.asarray(la2,float))[None,:]
    lo2 = np.radians(np.asarray(lo2,float))[None,:]
    a = np.sin((la2-la1)/2)**2 + np.cos(la1)*np.cos(la2)*np.sin((lo2-lo1)/2)**2
    return R * 2 * np.arcsin(np.sqrt(np.clip(a,0,1)))

def calc_camiones(kg):
    """
    Lógica corregida: SIEMPRE techo 28.500 kg/camión.
    El conteo de bultos ya no altera el cálculo.
    """
    try: kg = float(kg)
    except: return 1
    return max(1, int(np.ceil(kg / 28500.0)))

# ── SCORE DE OPORTUNIDAD ──────────────────────────────────────────────────────
def calcular_score_oportunidad(total_camiones, diff_pct, match_tipo, dias_ultimo_envio):
    """
    Score = camiones × factor_precio × factor_recencia × factor_match

    factor_precio:
      diff <= -20%  → 1.5  (gran ventaja)
      diff <= 0%    → 1.2  (ventaja moderada)
      diff <= 10%   → 0.9  (casi par)
      diff > 10%    → 0.6  (en desventaja, pero puede haber margen de negociación)
      sin precio    → 0.8

    factor_recencia:
      <= 60d  → 1.3  (activo recientemente)
      <= 120d → 1.0
      > 120d  → 0.7
      sin dato → 0.8

    factor_match:
      EXACTO  → 1.0
      CERCANO → 0.7
    """
    if diff_pct is None:
        fp = 0.8
    elif diff_pct <= -20:
        fp = 1.5
    elif diff_pct <= 0:
        fp = 1.2
    elif diff_pct <= 10:
        fp = 0.9
    else:
        fp = 0.6

    if dias_ultimo_envio is None:
        fr = 0.8
    elif dias_ultimo_envio <= 60:
        fr = 1.3
    elif dias_ultimo_envio <= 120:
        fr = 1.0
    else:
        fr = 0.7

    fm = 1.0 if match_tipo == 'EXACTO' else 0.7

    return round(total_camiones * fp * fr * fm, 1)

# ── CARGA ─────────────────────────────────────────────────────────────────────
def cargar_datos():
    global _cache
    eng = _engine()
    t0  = datetime.now()
    try:
        print(f'\n[INFO] Engine: {eng}')
        def leer(path, sheet, **kw):
            t = datetime.now()
            df = pd.read_excel(path, sheet_name=sheet, engine=eng, **kw)
            df.columns = [c.strip() for c in df.columns]
            print(f'  {os.path.basename(path)}: {len(df)} filas ({(datetime.now()-t).seconds}s)')
            return df

        hist = leer(HIST_FILE, 'Hoja1')
        impo = leer(IMPO_FILE, 'Detalle', dtype=str)
        expo = leer(EXPO_FILE, 'Detalle', dtype=str)

        print('[INFO] Procesando historial...')
        rutas = _proc_historial(hist)
        print(f'  → {len(rutas)} rutas')

        print('[INFO] Procesando Softtrade...')
        docs_i, docs_e, cats, trans = _proc_softtrade(impo, expo)
        print(f'  → {len(docs_i)} docs IMPO  |  {len(docs_e)} docs EXPO')

        print('[INFO] Matching...')
        prospectos = _matching(docs_i, docs_e, rutas)
        print(f'  → {len(prospectos)} prospectos')

        print(f'[OK] {(datetime.now()-t0).seconds}s\n')
        _cache.update({
            'prospectos': prospectos, 'rutas': rutas,
            'categorias': sorted(cats), 'transportistas': sorted(trans)[:300],
            'error': None, 'loaded_at': datetime.now().strftime('%d/%m/%Y %H:%M'),
        })
    except Exception as e:
        import traceback
        _cache['error'] = str(e)
        print(f'[ERROR] {e}'); traceback.print_exc()

# ── HISTORIAL ─────────────────────────────────────────────────────────────────
def _proc_historial(hist):
    df = hist[hist['ESTADO'] == 'EMBARQUE CONFIRMADO'].copy()
    df['_venta'] = df['VENTA'].apply(parsear_venta)
    df['_fecha'] = pd.to_datetime(df['FECHA'], errors='coerce').dt.date
    df = df[df['_venta'] > 0]

    hoy   = date.today()
    corte = hoy - timedelta(days=DIAS_RECIENTE)
    rutas = {}

    for _, row in df.iterrows():
        origen  = str(row.get('ORIGEN','')).strip()
        destino = str(row.get('DESTINO','')).strip()
        paso    = str(row.get('PASO FRONTERIZO','')).strip()
        if not origen or origen.lower() in _INVALIDOS: continue
        key = (origen, destino, paso)
        if key not in rutas:
            rutas[key] = {
                'origen':origen,'destino':destino,'paso':paso,
                'co':get_coords(origen),'cd':get_coords(destino),'viajes':[],
            }
        rutas[key]['viajes'].append({
            'fecha':      row['_fecha'],
            'venta':      row['_venta'],
            'fletero':    str(row.get('FLETERO','')).strip(),
            'mercaderia': str(row.get('MERCADERIA','')).strip(),
            'cliente':    str(row.get('CLIENTE','')).strip(),
        })

    resultado = []
    for r in rutas.values():
        vj = r['viajes']
        todas    = [v['venta'] for v in vj]
        recientes= [v['venta'] for v in vj if v['fecha'] and v['fecha'] >= corte]
        r['venta_promedio'] = round(sum(todas)/len(todas), 0)     if todas     else 0
        r['venta_reciente'] = round(sum(recientes)/len(recientes),0) if recientes else r['venta_promedio']
        r['n_viajes']       = len(vj)
        vj_ord = sorted(vj, key=lambda x: x['fecha'] or date.min, reverse=True)
        r['detalle_viajes'] = [
            {'fecha': v['fecha'].strftime('%d/%m/%Y') if v['fecha'] else '—',
             'venta': v['venta'], 'fletero': v['fletero'],
             'mercaderia': v['mercaderia'], 'cliente': v['cliente']}
            for v in vj_ord[:10]
        ]
        resultado.append(r)
    return resultado

# ── SOFTTRADE ─────────────────────────────────────────────────────────────────
def _proc_softtrade(impo, expo):
    all_cats = set(); all_trans = set()

    # ── IMPO: ARG → CHL ──────────────────────────────────────────────────────
    df = impo.copy()
    df['_emp'] = df['Importador'].str.strip()
    df = df[~df['_emp'].str.lower().isin(_INVALIDOS) & (df['_emp'].str.len() > 2)]
    df['_kg']    = pd.to_numeric(df['Kgs. Brutos'].str.replace(',','.', regex=False), errors='coerce').fillna(0)
    df['_flete'] = pd.to_numeric(df['Flete U$S'].str.replace(',','.', regex=False), errors='coerce').fillna(0)
    df['_fecha'] = pd.to_datetime(df['Fecha'], errors='coerce').dt.date
    df['_doc']   = df['Documento de Transporte'].str.strip()

    docs_i = df.groupby('_doc').agg(
        empresa       =('_emp',                  'first'),
        rut           =('RUT',                   'first'),
        transportista =('Transportista',          'first'),
        puerto_embarque=('Puerto de Embarque',    'first'),   # puede ser "OTROS ARGENTINA"
        paso          =('Puerto de Desembarque',  'first'),
        destino_str   =('Aduana',                 'first'),
        kg            =('_kg',                   'sum'),
        flete         =('_flete',                'sum'),
        fecha         =('_fecha',                'max'),
        mercaderia    =('Mercadería',             'first'),
    ).reset_index().rename(columns={'_doc':'documento'})

    docs_i = docs_i[(docs_i['flete'] >= FLETE_MIN) & (docs_i['flete'] <= FLETE_MAX)].copy()

    # Resolver origen: "OTROS ARGENTINA" → código de aduana del documento
    origenes = docs_i.apply(
        lambda r: resolver_origen_impo(r['puerto_embarque'], r['documento']), axis=1
    )
    docs_i['origen_str']   = origenes.apply(lambda x: x[0])
    docs_i['coords_origen']= origenes.apply(lambda x: x[1])
    docs_i['coords_destino']= docs_i['destino_str'].apply(get_coords)

    # Camiones: solo por peso, techo único 28.500
    docs_i['camiones']  = docs_i['kg'].apply(calc_camiones)
    docs_i['flete_cam'] = (docs_i['flete'] / docs_i['camiones']).round(0)
    docs_i['categoria'] = docs_i['mercaderia'].apply(categorizar_mercaderia)

    all_cats.update(docs_i['categoria'].unique())
    all_trans.update(t for t in docs_i['transportista'].dropna().unique()
                     if t.lower() not in _INVALIDOS)

    # ── EXPO: CHL → ARG ──────────────────────────────────────────────────────
    df_e = expo.copy()
    df_e['_emp'] = df_e['Exportador'].str.strip()
    df_e = df_e[~df_e['_emp'].str.lower().isin(_INVALIDOS) & (df_e['_emp'].str.len() > 2)]
    df_e['_kg']    = pd.to_numeric(df_e['Kgs. Brutos'].str.replace(',','.', regex=False), errors='coerce').fillna(0)
    df_e['_flete'] = pd.to_numeric(df_e['Flete U$S'].str.replace(',','.', regex=False), errors='coerce').fillna(0)
    df_e['_fecha'] = pd.to_datetime(df_e['Fecha'], errors='coerce').dt.date

    docs_e = df_e.groupby('DUA').agg(
        empresa       =('_emp',                    'first'),
        transportista =('Empresa Transportista',   'first'),
        origen_str    =('Aduana',                  'first'),
        paso          =('Puerto de Embarque',       'first'),
        destino_str   =('Puerto de Desembarque',    'first'),
        kg            =('_kg',                     'sum'),
        flete         =('_flete',                  'sum'),
        fecha         =('_fecha',                  'max'),
        mercaderia    =('Mercadería',               'first'),
    ).reset_index().rename(columns={'DUA':'documento'})

    docs_e = docs_e[(docs_e['flete'] >= FLETE_MIN) & (docs_e['flete'] <= FLETE_MAX)].copy()
    docs_e['coords_origen']  = docs_e['origen_str'].apply(get_coords)
    docs_e['coords_destino'] = docs_e['destino_str'].apply(get_coords)
    docs_e['camiones']  = docs_e['kg'].apply(calc_camiones)
    docs_e['flete_cam'] = (docs_e['flete'] / docs_e['camiones']).round(0)
    docs_e['categoria'] = docs_e['mercaderia'].apply(categorizar_mercaderia)
    docs_e['rut'] = ''

    all_cats.update(docs_e['categoria'].unique())
    all_trans.update(t for t in docs_e['transportista'].dropna().unique()
                     if t.lower() not in _INVALIDOS)

    all_cats.discard('Sin clasificar')
    return docs_i, docs_e, all_cats, all_trans

# ── MATCHING ──────────────────────────────────────────────────────────────────
def _matching(docs_i, docs_e, rutas):
    if not rutas: return []

    # Arrays de coordenadas de rutas
    rut_lo  = np.array([r['co'][0] if r['co'][0] is not None else np.nan for r in rutas])
    rut_lo_lon = np.array([r['co'][1] if r['co'][1] is not None else np.nan for r in rutas])
    rut_ld  = np.array([r['cd'][0] if r['cd'][0] is not None else np.nan for r in rutas])
    rut_ld_lon = np.array([r['cd'][1] if r['cd'][1] is not None else np.nan for r in rutas])

    hoy = date.today()

    def score_docs(docs, fuente):
        """
        Nuevo scoring con dos radios:
          Origen dentro de 50km:  +2  (EXACTO nivel)
          Origen 50-100km:        +1  (CERCANO nivel)
          Destino dentro de 50km: +2
          Destino 50-100km:       +1
          Mismo paso:             +1
        EXACTO: score >= 4  (origen Y destino dentro de 50km)
        CERCANO: score 2-3
        """
        docs = docs.copy()
        co_lat = docs['coords_origen'].apply(lambda x: x[0] if x else None)
        co_lon = docs['coords_origen'].apply(lambda x: x[1] if x else None)
        cd_lat = docs['coords_destino'].apply(lambda x: x[0] if x else None)
        cd_lon = docs['coords_destino'].apply(lambda x: x[1] if x else None)
        docs['co_lat'] = co_lat; docs['co_lon'] = co_lon
        docs['cd_lat'] = cd_lat; docs['cd_lon'] = cd_lon

        n = len(docs); m = len(rutas)
        score_mat = np.zeros((n, m), dtype=np.int8)

        # Puntuación origen
        mask_o = docs['co_lat'].notna().values
        if mask_o.any():
            idx = np.where(mask_o)[0]
            la = docs['co_lat'].values[mask_o]; lo = docs['co_lon'].values[mask_o]
            vr = ~np.isnan(rut_lo)
            dist = haversine_matrix(la, lo,
                                    np.where(vr, rut_lo, 0),
                                    np.where(vr, rut_lo_lon, 0))
            score_mat[np.ix_(idx, vr)] += np.where(dist[:,vr]<=RADIO_EXACTO, 2,
                                           np.where(dist[:,vr]<=RADIO_CERCANO, 1, 0)).astype(np.int8)

        # Puntuación destino
        mask_d = docs['cd_lat'].notna().values
        if mask_d.any():
            idx = np.where(mask_d)[0]
            la = docs['cd_lat'].values[mask_d]; lo = docs['cd_lon'].values[mask_d]
            vr = ~np.isnan(rut_ld)
            dist = haversine_matrix(la, lo,
                                    np.where(vr, rut_ld, 0),
                                    np.where(vr, rut_ld_lon, 0))
            score_mat[np.ix_(idx, vr)] += np.where(dist[:,vr]<=RADIO_EXACTO, 2,
                                           np.where(dist[:,vr]<=RADIO_CERCANO, 1, 0)).astype(np.int8)

        # Puntuación paso
        pasos_doc  = docs['paso'].fillna('').str.upper().str.strip().values
        pasos_ruta = [r['paso'] for r in rutas]
        for i, pd_ in enumerate(pasos_doc):
            if not pd_ or pd_ == 'NAN': continue
            for j, pr in enumerate(pasos_ruta):
                if pasos_coinciden(pr, pd_):
                    score_mat[i, j] += 1

        docs['_best_score'] = score_mat.max(axis=1)
        docs['_best_ruta']  = score_mat.argmax(axis=1)
        docs.loc[docs['_best_score'] < 2, '_best_ruta'] = -1
        return docs

    di = score_docs(docs_i, 'IMPO')
    de = score_docs(docs_e, 'EXPO')

    prospectos = {}

    def agrupar(docs, fuente):
        for _, row in docs.iterrows():
            score = int(row['_best_score'])
            if score < 2: continue
            emp   = str(row['empresa']).strip()
            key   = (emp, fuente)
            ri    = int(row['_best_ruta'])
            ruta  = rutas[ri] if ri >= 0 else None

            doc_info = {
                'documento':    str(row['documento']),
                'origen':       str(row['origen_str']),
                'destino':      str(row['destino_str']),
                'paso':         str(row['paso']),
                'transportista':str(row['transportista']),
                'kg_brutos':    float(row['kg']),
                'bultos':       None,
                'camiones':     int(row['camiones']),
                'flete_total':  float(row['flete']),
                'flete_cam':    float(row['flete_cam']),
                'fecha':        row['fecha'],
                'mercaderia':   str(row['mercaderia']),
                'categoria':    str(row['categoria']),
                'score':        score,
                'ruta_idx':     ri,
            }
            if fuente == 'IMPO':
                doc_info['bultos'] = None  # ya no usamos bultos en cálculo

            if key not in prospectos:
                prospectos[key] = {
                    'empresa': emp, 'rut': str(row.get('rut','')),
                    'fuente': fuente, 'docs': [],
                    'total_camiones': 0, 'flete_total': 0.0,
                    'ultima_fecha': None, 'best_score': 0, 'best_ruta_idx': -1,
                    'trans_set': set(), 'cat_set': set(),
                }
            p = prospectos[key]
            p['docs'].append(doc_info)
            p['total_camiones'] += int(row['camiones'])
            p['flete_total']    += float(row['flete'])
            if row['fecha'] and pd.notna(row['fecha']):
                if p['ultima_fecha'] is None or row['fecha'] > p['ultima_fecha']:
                    p['ultima_fecha'] = row['fecha']
            if score > p['best_score']:
                p['best_score'] = score; p['best_ruta_idx'] = ri
            t = str(row['transportista']).strip()
            c = str(row['categoria']).strip()
            if t and t.lower() not in _INVALIDOS: p['trans_set'].add(t)
            if c and c not in ('Sin clasificar','nan'): p['cat_set'].add(c)

    agrupar(di, 'IMPO')
    agrupar(de, 'EXPO')

    resultado = []
    for p in prospectos.values():
        if len(p['docs']) < DOCS_MIN: continue
        tc  = p['total_camiones']
        p['flete_mercado_cam'] = round(p['flete_total']/tc, 0) if tc > 0 else 0
        uf  = p['ultima_fecha']
        p['dias_ultimo_envio'] = (date.today()-uf).days if uf else None
        p['ultima_fecha_str']  = uf.strftime('%d/%m/%Y') if uf else ''
        p['num_docs']          = len(p['docs'])

        bs = p['best_score']
        p['match_tipo'] = 'EXACTO' if bs >= 4 else 'CERCANO' if bs >= 2 else None
        if not p['match_tipo']: continue

        ri = p['best_ruta_idx']
        mr = rutas[ri] if ri >= 0 else None
        p['ruta_mercotruck'] = {
            'origen':mr['origen'],'destino':mr['destino'],'paso':mr['paso'],
            'n_viajes':mr['n_viajes'],
            'venta_promedio':mr['venta_promedio'],'venta_reciente':mr['venta_reciente'],
            'detalle_viajes':mr['detalle_viajes'],
        } if mr else None

        vm = mr['venta_reciente'] if mr else 0
        p['flete_mercotruck_cam'] = vm
        p['diff_pct'] = (
            round((vm - p['flete_mercado_cam']) / p['flete_mercado_cam'] * 100, 1)
            if vm > 0 and p['flete_mercado_cam'] > 0 else None
        )
        p['transportistas_list'] = sorted(p['trans_set'])
        p['categorias_list']     = sorted(p['cat_set'])

        # Score de oportunidad (para sort por defecto)
        p['score_oportunidad'] = calcular_score_oportunidad(
            tc, p['diff_pct'], p['match_tipo'], p['dias_ultimo_envio']
        )
        resultado.append(p)

    # Ordenar por score de oportunidad descendente
    resultado.sort(key=lambda x: -x['score_oportunidad'])
    return resultado

# ── API ───────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    from flask import make_response
    resp = make_response(render_template_string(HTML))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/status')
def api_status():
    p = _cache['prospectos'] or []
    r = _cache['rutas'] or []
    return jsonify({
        'loaded': len(p)>0, 'error':_cache['error'],
        'loaded_at':_cache['loaded_at'],
        'prospectos':len(p), 'rutas':len(r),
    })

@app.route('/api/categorias')
def api_categorias():
    return jsonify({'categorias': _cache.get('categorias', [])})

@app.route('/api/reload')
def api_reload():
    cargar_datos(); return jsonify({'ok':True,'error':_cache['error']})

@app.route('/api/buscar')
def api_buscar():
    prospectos = _cache.get('prospectos')
    if not prospectos:
        return jsonify({'error':'Datos cargando, esperá unos segundos...','clientes':[]})

    fuente_f = request.args.get('fuente','').upper()
    tipo_f   = request.args.get('tipo','').upper()

    resultado = []
    for p in prospectos:
        if fuente_f and p['fuente'] != fuente_f: continue
        if tipo_f   and p['match_tipo'] != tipo_f: continue

        docs_out = []
        for d in p['docs']:
            docs_out.append({
                'documento':    d['documento'],
                'origen':       d['origen'],
                'destino':      d['destino'],
                'paso':         d['paso'],
                'transportista':d['transportista'],
                'kg_brutos':    round(d['kg_brutos'],0),
                'camiones':     d['camiones'],
                'flete_total':  round(d['flete_total'],0),
                'flete_cam':    d['flete_cam'],
                'fecha':        d['fecha'].strftime('%d/%m/%Y') if d['fecha'] and pd.notna(d['fecha']) else '',
                'mercaderia':   d['mercaderia'],
                'categoria':    d['categoria'],
            })

        rm = p.get('ruta_mercotruck')
        resultado.append({
            'empresa':             p['empresa'],
            'rut':                 p.get('rut',''),
            'fuente':              p['fuente'],
            'transportistas_list': p.get('transportistas_list',[]),
            'categorias_list':     p.get('categorias_list',[]),
            'total_camiones':      p['total_camiones'],
            'flete_mercado_cam':   p['flete_mercado_cam'],
            'flete_mercotruck_cam':p.get('flete_mercotruck_cam',0),
            'diff_pct':            p.get('diff_pct'),
            'match_tipo':          p['match_tipo'],
            'score_oportunidad':   p.get('score_oportunidad',0),
            'ruta_mercotruck':     rm,
            'dias_ultimo_envio':   p.get('dias_ultimo_envio'),
            'ultima_fecha':        p.get('ultima_fecha_str',''),
            'num_docs':            p['num_docs'],
            'docs':                docs_out,
            'key':                 f"{p['empresa']}_{p['fuente']}",
        })

    return jsonify({'clientes':resultado,'total':len(resultado)})

@app.route('/api/exportar')
def api_exportar():
    data = api_buscar().get_json()
    clientes = data.get('clientes',[])
    out = io.StringIO()
    w = csv.writer(out, delimiter=';')
    w.writerow(['Empresa','RUT','Fuente','Score Oportunidad','Transportistas',
                'Categorías','Total Camiones','Flete Mercado USD/cam',
                'Flete Mercotruck USD/cam','Diferencia %','Match',
                'Ruta Mercotruck','Días último envío','Última Fecha','Nº Docs'])
    for c in clientes:
        rm   = c['ruta_mercotruck']
        ruta = f"{rm['origen']} → {rm['destino']} ({rm['paso']})" if rm else ''
        w.writerow([
            c['empresa'],c['rut'],c['fuente'],c['score_oportunidad'],
            ' | '.join(c['transportistas_list'][:3]),
            ' | '.join(c['categorias_list'][:3]),
            c['total_camiones'],c['flete_mercado_cam'],c['flete_mercotruck_cam'],
            f"{c['diff_pct']:+.1f}%" if c['diff_pct'] is not None else '',
            c['match_tipo'],ruta,
            c['dias_ultimo_envio'] if c['dias_ultimo_envio'] is not None else '',
            c['ultima_fecha'],c['num_docs'],
        ])
    out.seek(0)
    return Response('\ufeff'+out.getvalue(),mimetype='text/csv; charset=utf-8-sig',
                    headers={'Content-Disposition':'attachment; filename=mercotruck_prospectos.csv'})

# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mercotruck — Prospectos</title>
<style>
:root{--dk:#0D1117;--tl:#1B5E6B;--tl2:#2a7d8e;--rd:#C0392B;
  --li:#F4F6F8;--br:#DEE2E6;--tx:#212529;--mu:#6C757D;
  --gn:#1A7A3C;--am:#B8680A}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:var(--li);color:var(--tx);font-size:13px}

header{background:var(--dk);color:#fff;padding:11px 20px;display:flex;
  align-items:center;justify-content:space-between;
  position:sticky;top:0;z-index:100;box-shadow:0 2px 8px rgba(0,0,0,.4)}
.logo{font-size:18px;font-weight:700;letter-spacing:1px}
.logo em{color:var(--tl2);font-style:normal}

#sb{background:var(--tl);color:#fff;padding:6px 20px;font-size:12px;
  display:flex;align-items:center;gap:10px;flex-wrap:wrap}
#sb.er{background:var(--rd)}
.dot{width:7px;height:7px;border-radius:50%;background:#4CAF50}
.dot.e{background:#fc0}

.fl{background:#fff;padding:10px 20px;border-bottom:1px solid var(--br)}
.fr{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:6px}
.fr:last-child{margin:0}
.fl label{font-size:11px;font-weight:600;color:var(--mu);white-space:nowrap}
select,input[type=text]{height:30px;padding:0 9px;border:1px solid var(--br);
  border-radius:5px;font-size:12px;background:#fff}
select:focus,input:focus{outline:2px solid var(--tl);border-color:transparent}
input[type=text]{min-width:130px}

.btn{height:30px;padding:0 13px;border:none;border-radius:5px;
  font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap}
.bp{background:var(--tl);color:#fff}.bp:hover{background:var(--tl2)}
.bo{background:#fff;border:1px solid var(--br);color:var(--tx)}.bo:hover{background:var(--li)}
.sp{width:1px;height:22px;background:var(--br)}

.st{display:flex;gap:7px;padding:9px 20px;background:#fff;
  border-bottom:1px solid var(--br);flex-wrap:wrap;align-items:center}
.sc{background:var(--li);border-radius:6px;padding:6px 13px;
  min-width:95px;text-align:center;border:1px solid var(--br)}
.sc .n{font-size:19px;font-weight:700;color:var(--tl);line-height:1}
.sc .l{font-size:10px;color:var(--mu);margin-top:2px}
.pg{margin-left:auto;display:flex;align-items:center;gap:6px;font-size:12px;color:var(--mu)}

.tw{padding:14px 20px;overflow-x:auto}
table{width:100%;border-collapse:collapse;font-size:12px;background:#fff;
  border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,.08)}
thead tr{background:var(--dk);color:#fff}
th{padding:9px 10px;text-align:left;font-weight:600;font-size:11px;
  white-space:nowrap;cursor:pointer;user-select:none}
th:hover{background:var(--tl)}
tbody tr{border-bottom:1px solid var(--br)}
tbody tr:hover{background:#f0f7f9}
td{padding:7px 10px;vertical-align:top}
.sub{font-size:10px;color:var(--mu);margin-top:1px}
.rt{font-size:10px;color:var(--tl);margin-top:1px}
.tag{display:inline-block;background:#e8f4f8;color:var(--tl);
  border-radius:3px;padding:1px 5px;font-size:10px;margin:1px}
.cat-tag{display:inline-block;background:#f3e8ff;color:#6f42c1;
  border-radius:3px;padding:1px 5px;font-size:10px;margin:1px}

.bx{display:inline-block;padding:2px 7px;border-radius:20px;font-size:10px;font-weight:700}
.bex{background:#d4edda;color:var(--gn)}.bce{background:#fff3cd;color:var(--am)}
.bim{background:#cce5ff;color:#004085}.bep{background:#f8d7da;color:#721c24}
.pb{color:var(--gn);font-weight:700}.pw{color:var(--rd);font-weight:700}
.an{color:var(--gn);font-weight:600}.am2{color:var(--am);font-weight:600}.ao{color:var(--rd);font-weight:600}

/* Score oportunidad visual */
.opp{display:inline-block;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700}
.opp-a{background:#d4edda;color:var(--gn)}
.opp-b{background:#e8f4f8;color:var(--tl)}
.opp-c{background:#fff3cd;color:var(--am)}
.opp-d{background:#f8d7da;color:var(--rd)}

.xb{background:none;border:none;cursor:pointer;color:var(--tl);font-size:13px;padding:0 2px}
.dr td{background:#f7fbfc;padding:0;border-bottom:2px solid var(--tl)}
.di{padding:8px 12px}
.di table{box-shadow:none;border-radius:0;font-size:11px}
.di thead tr{background:var(--tl)}
.di th,.di td{padding:5px 8px}
/* paginación interna de docs */
.doc-pag{display:flex;gap:5px;align-items:center;margin-top:6px;font-size:11px;color:var(--mu)}
.doc-pag button{padding:2px 8px;border:1px solid var(--br);border-radius:4px;
  background:#fff;cursor:pointer;font-size:11px}
.doc-pag button:hover{background:var(--li)}
.doc-pag button:disabled{opacity:.4;cursor:default}

.ov{display:none;position:fixed;inset:0;background:rgba(0,0,0,.55);
  z-index:200;align-items:center;justify-content:center}
.ov.on{display:flex}
.mo{background:#fff;border-radius:10px;width:640px;max-width:96vw;
  max-height:90vh;overflow-y:auto;box-shadow:0 8px 40px rgba(0,0,0,.3);padding:22px}
.mo h3{color:var(--tl);margin-bottom:12px}
.mf{margin-bottom:7px;font-size:12px}.mf strong{color:var(--dk)}
.mg{display:grid;grid-template-columns:1fr 1fr;gap:6px 16px;margin-bottom:12px}
.scr{background:var(--li);border-radius:6px;padding:11px;font-size:12px;
  line-height:1.7;border-left:4px solid var(--tl);margin-top:10px;
  font-style:italic;color:#333;white-space:pre-wrap}
.cl{float:right;background:var(--br);border:none;border-radius:50%;
  width:25px;height:25px;cursor:pointer;font-size:14px;line-height:25px;
  text-align:center}.cl:hover{background:var(--rd);color:#fff}
.cpbtn{margin-top:8px;height:30px;padding:0 14px;background:var(--tl);
  color:#fff;border:none;border-radius:5px;cursor:pointer;font-size:12px;font-weight:600}
.cpbtn:hover{background:var(--tl2)}.cpbtn.ok{background:var(--gn)}
.ht{width:100%;font-size:11px;border-collapse:collapse;margin-top:8px}
.ht th{background:#e8f4f8;padding:5px 7px;text-align:left;font-weight:600}
.ht td{padding:4px 7px;border-bottom:1px solid var(--br)}
.ht tr:hover td{background:#f7fbfc}
.rc{background:#d4edda;color:var(--gn);border-radius:3px;padding:1px 4px;font-size:10px}

#ld{text-align:center;padding:50px;color:var(--mu);display:none}
.sp2{width:30px;height:30px;border:4px solid var(--br);border-top-color:var(--tl);
  border-radius:50%;animation:sp .7s linear infinite;margin:0 auto 10px}
@keyframes sp{to{transform:rotate(360deg)}}
.emp{text-align:center;padding:40px;color:var(--mu)}
#dg{display:none;background:#fff8e1;border:1px solid #ffe082;border-radius:6px;
  padding:9px 14px;margin:4px 20px;font-size:11px;font-family:monospace;
  white-space:pre-wrap;max-height:180px;overflow-y:auto}
</style>
</head>
<body>

<header>
  <div class="logo">MERCO<em>TRUCK</em>
    <span style="font-weight:300;font-size:12px;margin-left:8px;color:#aaa">Buscador de Clientes v5.3</span>
  </div>
  <div style="font-size:11px;color:#aaa" id="hi">Iniciando...</div>
</header>

<div id="sb">
  <div class="dot" id="sd"></div>
  <span id="st">Cargando datos...</span>
  <button class="btn bo" style="height:24px;font-size:11px" onclick="reload()">↺ Recargar</button>
  <button class="btn bo" style="height:24px;font-size:11px" onclick="tgDiag()">🔍 Info</button>
</div>
<div id="dg"></div>

<div class="fl">
  <div class="fr">
    <label>Fuente:</label>
    <select id="ff" onchange="search()">
      <option value="">IMPO + EXPO</option>
      <option value="IMPO">IMPO (ARG→CHL)</option>
      <option value="EXPO">EXPO (CHL→ARG)</option>
    </select>
    <label>Match:</label>
    <select id="fm2" onchange="search()">
      <option value="">Todos</option>
      <option value="EXACTO">EXACTO</option>
      <option value="CERCANO">CERCANO</option>
    </select>
    <div class="sp"></div>
    <label>Empresa / RUT:</label>
    <input type="text" id="fe" placeholder="Buscar..." oninput="lf()">
    <label>Transportista:</label>
    <input type="text" id="ftr" placeholder="Buscar..." oninput="lf()">
    <label>Categoría:</label>
    <select id="fcat" onchange="lf()">
      <option value="">Todas las categorías</option>
    </select>
  </div>
  <div class="fr">
    <button class="btn bp" onclick="search()">🔎 Buscar</button>
    <button class="btn bo" onclick="clearAll()">✕ Limpiar</button>
    <button class="btn bo" onclick="xport()">⬇ CSV</button>
  </div>
</div>

<div class="st" id="sts" style="display:none">
  <div class="sc"><div class="n" id="s0">0</div><div class="l">Encontrados</div></div>
  <div class="sc"><div class="n" id="s1">0</div><div class="l">EXACTO</div></div>
  <div class="sc"><div class="n" id="s2">0</div><div class="l">CERCANO</div></div>
  <div class="sc"><div class="n" id="s3">0</div><div class="l">Camiones</div></div>
  <div class="sc"><div class="n" id="s4">0</div><div class="l">IMPO</div></div>
  <div class="sc"><div class="n" id="s5">0</div><div class="l">EXPO</div></div>
  <div class="pg">
    <button class="btn bo" id="bp" onclick="chPg(-1)" disabled>← Ant</button>
    <span id="pt">Pág 1 / 1</span>
    <button class="btn bo" id="bn" onclick="chPg(1)">Sig →</button>
  </div>
</div>

<div class="tw">
  <div id="ld"><div class="sp2"></div>Procesando...</div>
  <div id="res"></div>
</div>

<div class="ov" id="ov" onclick="close2(event)">
  <div class="mo">
    <button class="cl" onclick="close2()">✕</button>
    <h3>📋 Detalle del Prospecto</h3>
    <div id="mb"></div>
  </div>
</div>

<script>
const PER=50, DOC_PER=10;
let all=[],fil=[],pg=1,sk='score_oportunidad',sa=false;
// Estado interno de paginación de docs por empresa key
const docPages = {};
const fmt=n=>Number(n||0).toLocaleString('es-AR');

async function chkStatus(){
  try{
    const d=await fetch('/api/status').then(r=>r.json());
    const sb=document.getElementById('sb'),sd=document.getElementById('sd');
    if(d.error){sb.className='er';sd.className='dot e';
      document.getElementById('st').textContent='⚠ '+d.error;
    }else if(d.loaded){sb.className='';sd.className='dot';
      document.getElementById('st').textContent=
        `✓ ${fmt(d.prospectos)} prospectos · ${fmt(d.rutas)} rutas · ${d.loaded_at}`;
      document.getElementById('hi').textContent=d.loaded_at;
      if(!all.length) search();
    }else{document.getElementById('st').textContent='Cargando...';setTimeout(chkStatus,2000);}
  }catch(e){setTimeout(chkStatus,3000);}
}

async function search(){
  document.getElementById('ld').style.display='block';
  document.getElementById('res').innerHTML='';
  document.getElementById('sts').style.display='none';
  const p=new URLSearchParams();
  const ff=document.getElementById('ff').value;
  const fm=document.getElementById('fm2').value;
  if(ff)p.set('fuente',ff);if(fm)p.set('tipo',fm);
  try{
    const d=await fetch('/api/buscar?'+p).then(r=>r.json());
    document.getElementById('ld').style.display='none';
    if(d.error){document.getElementById('res').innerHTML=`<div class="emp">⚠ ${d.error}</div>`;return;}
    all=d.clientes||[];fil=[...all];pg=1;
    lf(false);
  }catch(e){
    document.getElementById('ld').style.display='none';
    document.getElementById('res').innerHTML='<div class="emp">Error de conexión.</div>';
  }
}

function lf(redraw=true){
  const qe=document.getElementById('fe').value.toLowerCase().trim();
  const qt=document.getElementById('ftr').value.toLowerCase().trim();
  const qc=document.getElementById('fcat').value.toLowerCase().trim();  fil=all.filter(x=>{
    if(qe&&!x.empresa.toLowerCase().includes(qe)&&!(x.rut||'').includes(qe))return false;
    if(qt&&!x.transportistas_list.some(t=>t.toLowerCase().includes(qt)))return false;
    if(qc&&!x.categorias_list.some(c=>c.toLowerCase().includes(qc)))return false;
    return true;
  });
  if(redraw)pg=1;
  renderStats(fil);renderTable();
}

function clearAll(){
  ['ff','fm2','fcat'].forEach(id=>document.getElementById(id).value='');
  ['fe','ftr'].forEach(id=>document.getElementById(id).value='');
  search();
}

function renderStats(d){
  const ex=d.filter(x=>x.match_tipo==='EXACTO').length;
  const ce=d.filter(x=>x.match_tipo==='CERCANO').length;
  const cam=d.reduce((s,x)=>s+(x.total_camiones||0),0);
  const im=d.filter(x=>x.fuente==='IMPO').length;
  const ep=d.filter(x=>x.fuente==='EXPO').length;
  ['s0','s1','s2','s3','s4','s5'].forEach((id,i)=>
    document.getElementById(id).textContent=fmt([d.length,ex,ce,cam,im,ep][i]));
  document.getElementById('sts').style.display='flex';
}

function chPg(d){const tot=Math.ceil(fil.length/PER);pg=Math.max(1,Math.min(tot,pg+d));renderTable();}

function sortBy(col){
  sk===col?sa=!sa:(sk=col,sa=false);
  fil.sort((a,b)=>{
    let va=a[col],vb=b[col];
    if(va==null)va=sa?Infinity:-Infinity;if(vb==null)vb=sa?Infinity:-Infinity;
    if(typeof va==='string')return sa?va.localeCompare(vb):vb.localeCompare(va);
    return sa?va-vb:vb-va;
  });
  renderTable();
}
const ar=c=>sk!==c?'<span style="opacity:.35">⇅</span>':sa?'↑':'↓';

// Score visual
function oppBadge(score){
  const cls=score>=2000?'opp-a':score>=800?'opp-b':score>=300?'opp-c':'opp-d';
  return `<span class="opp ${cls}">${Math.round(score)}</span>`;
}

function renderTable(){
  const tot=Math.ceil(fil.length/PER)||1;
  document.getElementById('pt').textContent=`Pág ${pg} / ${tot}`;
  document.getElementById('bp').disabled=pg<=1;
  document.getElementById('bn').disabled=pg>=tot;

  const slice=fil.slice((pg-1)*PER,pg*PER);
  if(!slice.length){document.getElementById('res').innerHTML='<div class="emp">Sin resultados.</div>';return;}

  const thead=`<thead><tr>
    <th onclick="sortBy('score_oportunidad')">Oportunidad ${ar('score_oportunidad')}</th>
    <th onclick="sortBy('empresa')">Empresa ${ar('empresa')}</th>
    <th>Fuente</th>
    <th onclick="sortBy('transportista')">Transportistas ${ar('transportista')}</th>
    <th>Ruta</th>
    <th onclick="sortBy('total_camiones')" style="text-align:right">Cam. ${ar('total_camiones')}</th>
    <th onclick="sortBy('flete_mercado_cam')" style="text-align:right">Mercado ${ar('flete_mercado_cam')}</th>
    <th onclick="sortBy('flete_mercotruck_cam')" style="text-align:right">Mercotruck ${ar('flete_mercotruck_cam')}</th>
    <th onclick="sortBy('diff_pct')" style="text-align:right">Dif. % ${ar('diff_pct')}</th>
    <th onclick="sortBy('dias_ultimo_envio')">Ult.envío ${ar('dias_ultimo_envio')}</th>
    <th>Match</th>
    <th></th>
  </tr></thead>`;

  const rows=slice.map((r,i)=>{
    const idx=(pg-1)*PER+i;
    const bc=r.match_tipo==='EXACTO'?'bex':'bce';
    const bf=r.fuente==='IMPO'?'bim':'bep';

    // Precio Mercotruck (celda separada del %)
    const pMT = r.flete_mercotruck_cam>0
      ? '$'+Math.round(r.flete_mercotruck_cam).toLocaleString('es-AR')
      : '—';
    let pDif = '—';
    if(r.diff_pct!=null){
      const c=r.diff_pct<=0?'pb':'pw', s=r.diff_pct>0?'+':'';
      pDif=`<span class="${c}" style="font-size:12px;font-weight:700">${s}${r.diff_pct}%</span>`;
    }

    let eH=r.ultima_fecha||'—';
    if(r.dias_ultimo_envio!=null){
      const c=r.dias_ultimo_envio<=60?'an':r.dias_ultimo_envio<=120?'am2':'ao';
      eH=`<span class="${c}">${r.dias_ultimo_envio}d</span><div class="sub">${r.ultima_fecha}</div>`;
    }

    const rH=r.ruta_mercotruck
      ?`<div class="rt">✓ ${r.ruta_mercotruck.origen} → ${r.ruta_mercotruck.destino}</div>
        <div class="rt">⛰ ${r.ruta_mercotruck.paso}</div>`:'—';

    const cats=(r.categorias_list||[]).slice(0,2).map(c=>`<span class="cat-tag">${c}</span>`).join('');
    const trs=(r.transportistas_list||[]).slice(0,2).join('<br>');

    return `<tr>
      <td>${oppBadge(r.score_oportunidad)}</td>
      <td>
        <strong>${r.empresa}</strong>
        <div class="sub">${r.rut||''}</div>
        <div style="margin-top:3px">${cats}</div>
      </td>
      <td><span class="bx ${bf}">${r.fuente}</span></td>
      <td style="max-width:150px;font-size:11px">${trs||'—'}</td>
      <td>${rH}</td>
      <td style="text-align:right"><strong>${fmt(r.total_camiones)}</strong>
        <div class="sub">${r.num_docs} doc.</div></td>
      <td style="text-align:right">
        ${r.flete_mercado_cam>0?'$'+Math.round(r.flete_mercado_cam).toLocaleString('es-AR'):'—'}
        <div class="sub">USD/cam</div></td>
      <td style="text-align:right">${pMT}<div class="sub">USD/cam</div></td>
      <td style="text-align:right">${pDif}</td>
      <td>${eH}</td>
      <td><span class="bx ${bc}">${r.match_tipo}</span></td>
      <td style="white-space:nowrap">
        <button class="xb" onclick="togD(${idx},this)" title="Ver documentos">▶</button>
        <button class="btn bp" style="height:24px;padding:0 10px;font-size:12px;margin-left:3px;font-weight:700"
                onclick="ficha(${idx})" title="Ver detalle">+</button>
      </td>
    </tr>
    <tr class="dr" id="dr-${idx}" style="display:none">
      <td colspan="12"><div class="di" id="di-${idx}">${rDocsPage(r,0)}</div></td>
    </tr>`;
  }).join('');

  document.getElementById('res').innerHTML=`<table>${thead}<tbody>${rows}</tbody></table>`;
}

// ── Docs paginados ─────────────────────────────────────────────────────────────
function rDocsPage(r, pg_doc){
  const docs=r.docs||[];
  const tot=Math.ceil(docs.length/DOC_PER)||1;
  const slice=docs.slice(pg_doc*DOC_PER,(pg_doc+1)*DOC_PER);
  const rows=slice.map(d=>`<tr>
    <td>${d.documento}</td>
    <td>${d.origen||'—'}</td>
    <td>${d.destino||'—'}</td>
    <td>${d.paso||'—'}</td>
    <td>${d.transportista||'—'}</td>
    <td style="text-align:right">${Math.round(d.kg_brutos).toLocaleString('es-AR')} kg</td>
    <td style="text-align:right"><strong>${d.camiones}</strong></td>
    <td style="text-align:right">${d.flete_cam>0?'$'+Math.round(d.flete_cam).toLocaleString('es-AR'):'—'}</td>
    <td>${d.fecha||'—'}</td>
    <td>${d.mercaderia||'—'}</td>
    <td><span class="cat-tag">${d.categoria||'—'}</span></td>
  </tr>`).join('');

  const pagCtrl=tot>1?`
    <div class="doc-pag">
      <button onclick="chDocPg('${r.key}',${pg_doc-1})" ${pg_doc<=0?'disabled':''}>←</button>
      <span>${pg_doc+1} / ${tot}</span>
      <button onclick="chDocPg('${r.key}',${pg_doc+1})" ${pg_doc>=tot-1?'disabled':''}>→</button>
      <span style="color:var(--mu)">${docs.length} documentos total</span>
    </div>`:'';

  return `<table><thead><tr>
    <th>Documento</th><th>Origen</th><th>Destino</th><th>Paso</th><th>Transportista</th>
    <th>Kg</th><th>Cam.</th><th>Flete/cam</th><th>Fecha</th><th>Mercadería</th><th>Categoría</th>
  </tr></thead><tbody>${rows}</tbody></table>${pagCtrl}`;
}

// Mapa de key → {idx, pg_doc}
const docState = {};

function togD(idx,btn){
  const row=document.getElementById('dr-'+idx), v=row.style.display!=='none';
  row.style.display=v?'none':'table-row'; btn.textContent=v?'▶':'▼';
}

function chDocPg(key, new_pg){
  // Encontrar el prospecto por key
  const r=fil.find(x=>x.key===key); if(!r) return;
  const idx=fil.indexOf(r);
  const realIdx=(pg-1)*PER+fil.slice((pg-1)*PER,pg*PER).indexOf(r);
  const di=document.getElementById('di-'+realIdx);
  if(di) di.innerHTML=rDocsPage(r, new_pg);
}

// ── Ficha ──────────────────────────────────────────────────────────────────────
function ficha(idx){
  const r=fil[idx]; if(!r) return;
  const fm  =r.flete_mercado_cam>0?'$'+Math.round(r.flete_mercado_cam).toLocaleString('es-AR')+' USD/cam':'no disponible';
  const fmr =r.flete_mercotruck_cam>0?'$'+Math.round(r.flete_mercotruck_cam).toLocaleString('es-AR')+' USD/cam':'a consultar';
  const dir =r.fuente==='IMPO'?'Argentina → Chile':'Chile → Argentina';
  const rm  =r.ruta_mercotruck;
  const ruta=rm?`${rm.origen} → ${rm.destino} (${rm.paso})`:'—';

  let vent='';
  if(r.diff_pct!=null){
    vent=r.diff_pct<=0
      ?`<strong style="color:var(--gn)">Mercotruck ${Math.abs(r.diff_pct)}% POR DEBAJO del mercado</strong> — ventaja competitiva.`
      :`<span style="color:var(--rd)">Mercotruck ${r.diff_pct}% por encima del mercado</span> — negociar o revisar.`;
  }

  let histH='';
  if(rm&&rm.detalle_viajes&&rm.detalle_viajes.length){
    const hoy=new Date();
    const hrows=rm.detalle_viajes.map(v=>{
      const dias=v.fecha!=='—'?Math.round((hoy-new Date(v.fecha.split('/').reverse().join('-')))/86400000):null;
      const rc=dias!==null&&dias<=90?'<span class="rc">reciente</span>':'';
      return `<tr>
        <td>${v.fecha} ${rc}</td>
        <td><strong>$${Math.round(v.venta).toLocaleString('es-AR')}</strong></td>
        <td>${v.fletero||'—'}</td><td>${v.cliente||'—'}</td><td>${v.mercaderia||'—'}</td>
      </tr>`;
    }).join('');
    histH=`<div style="margin-top:14px">
      <div style="font-weight:600;font-size:11px;color:var(--mu);margin-bottom:4px">
        HISTORIAL MERCOTRUCK — ${ruta}
        · <strong>${rm.n_viajes} viajes</strong>
        · Prom. histórico: <strong>$${Math.round(rm.venta_promedio).toLocaleString('es-AR')}</strong>
        · <span style="color:var(--tl)">Precio 90d: <strong>$${Math.round(rm.venta_reciente).toLocaleString('es-AR')}</strong></span>
      </div>
      <table class="ht"><thead><tr>
        <th>Fecha</th><th>Venta USD</th><th>Fletero</th><th>Cliente</th><th>Mercadería</th>
      </tr></thead><tbody>${hrows}</tbody></table>
    </div>`;
  }

  const transActual=(r.transportistas_list||[]).slice(0,2).join(' / ')||'otro operador';
  const mercP=(r.categorias_list||[]).slice(0,2).join(' y ')||'su carga';
  const ahorro=r.diff_pct!=null&&r.diff_pct<=0?`Eso implica un ahorro del ${Math.abs(r.diff_pct)}% respecto a lo que pagan actualmente.\n\n`:'';
  const opp=`Score de oportunidad: ${Math.round(r.score_oportunidad||0)}`;

  const script=`"Buenos días, ¿hablo con el área de logística de ${r.empresa}?\n\n`+
    `Les llamo de Mercotruck, transportista especializado en ${dir}.\n\n`+
    `Vemos que mueven ${mercP} y trabajan con ${transActual}. `+
    `Operamos esa ruta —${ruta}— con frecuencia y podemos ofrecerles ${fmr} por camión.\n\n`+
    `${ahorro}`+
    `¿Tienen disponibilidad para una reunión breve esta semana?"`;

  document.getElementById('mb').innerHTML=`
    <div class="mg">
      <div class="mf"><strong>Empresa:</strong> ${r.empresa}</div>
      <div class="mf"><strong>RUT:</strong> ${r.rut||'—'}</div>
      <div class="mf"><strong>Fuente:</strong> <span class="bx ${r.fuente==='IMPO'?'bim':'bep'}">${r.fuente}</span> · ${dir}</div>
      <div class="mf"><strong>Match:</strong> <span class="bx ${r.match_tipo==='EXACTO'?'bex':'bce'}">${r.match_tipo}</span></div>
      <div class="mf"><strong>Transportistas:</strong><br><span style="font-size:11px">${(r.transportistas_list||[]).slice(0,4).join('<br>')||'—'}</span></div>
      <div class="mf"><strong>Categorías:</strong><br>${(r.categorias_list||[]).map(c=>`<span class="cat-tag">${c}</span>`).join(' ')||'—'}</div>
      <div class="mf"><strong>Ruta:</strong> ${ruta}</div>
      <div class="mf"><strong>Camiones / Docs:</strong> ${fmt(r.total_camiones)} cam · ${r.num_docs} docs</div>
      <div class="mf"><strong>Flete mercado:</strong> ${fm}</div>
      <div class="mf"><strong>Flete Mercotruck:</strong> ${fmr}</div>
    </div>
    ${vent?`<div style="padding:7px 10px;background:#f8f9fa;border-radius:5px;margin-bottom:10px;font-size:12px">${vent}</div>`:''}
    <div class="mf"><strong>Último envío:</strong> ${r.dias_ultimo_envio!=null?r.dias_ultimo_envio+'d atrás ('+r.ultima_fecha+')':r.ultima_fecha||'—'}</div>
    <div class="mf" style="color:var(--mu);font-size:11px">${opp}</div>
    ${histH}
    <hr style="margin:12px 0">
    <div style="font-weight:600;font-size:11px;color:var(--mu);margin-bottom:4px">SCRIPT SUGERIDO:</div>
    <div class="scr" id="scrtxt">${script}</div>
    <button class="cpbtn" id="cpbtn" onclick="copyScript()">📋 Copiar script</button>
  `;
  document.getElementById('ov').classList.add('on');
}

function copyScript(){
  const t=document.getElementById('scrtxt').innerText;
  navigator.clipboard.writeText(t).then(()=>{
    const b=document.getElementById('cpbtn');
    b.textContent='✓ Copiado!';b.classList.add('ok');
    setTimeout(()=>{b.textContent='📋 Copiar script';b.classList.remove('ok');},2000);
  });
}

function close2(e){
  if(!e||e.target===document.getElementById('ov')||e.target.classList.contains('cl'))
    document.getElementById('ov').classList.remove('on');
}

function xport(){window.location.href='/api/exportar';}

async function reload(){
  document.getElementById('st').textContent='Recargando...';
  all=[];fil=[];
  document.getElementById('res').innerHTML='';
  document.getElementById('sts').style.display='none';
  await fetch('/api/reload');
  setTimeout(chkStatus,500);
}

async function tgDiag(){
  const d=document.getElementById('dg');
  if(d.style.display==='block'){d.style.display='none';return;}
  d.style.display='block';d.textContent='...';
  const r=await fetch('/api/status').then(x=>x.json());
  d.textContent=JSON.stringify(r,null,2);
}

async function cargarCategorias(){
  try{
    const d=await fetch('/api/categorias').then(r=>r.json());
    const sel=document.getElementById('fcat');
    (d.categorias||[]).forEach(c=>{
      const opt=document.createElement('option');
      opt.value=c; opt.textContent=c;
      sel.appendChild(opt);
    });
  }catch(e){}
}

chkStatus();
cargarCategorias();
</script>
</body>
</html>"""

# ── ARRANQUE ──────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print('='*62)
    print('  Mercotruck  v5.3  —  Buscador de Clientes Potenciales')
    print('='*62)
    print(f'  Historial : {HIST_FILE}')
    print(f'  IMPO      : {IMPO_FILE}')
    print(f'  EXPO      : {EXPO_FILE}')
    print()
    cargar_datos()
    print('  → http://localhost:5000')
    print('='*62)
    app.run(debug=False, port=5000)