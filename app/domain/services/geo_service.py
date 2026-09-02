import numpy as np

# ADUANAS ARGENTINAS (Código de aduana -> Nombre, (Lat, Lon))
ADUANAS = {
    '001': ('Bs.As. Capital',      (-34.603, -58.381)),
    '003': ('Bahía Blanca',         (-38.719, -62.270)),
    '004': ('Bahía Blanca',         (-38.719, -62.270)),
    '005': ('Barranqueras',         (-27.484, -58.941)),
    '006': ('Bs.As. Palermo',       (-34.588, -58.416)),
    '007': ('Campana',              (-34.163, -58.959)),
    '008': ('Campana',              (-34.163, -58.959)),
    '009': ('Clorinda',             (-25.283, -57.722)),
    '010': ('Comodoro Rivadavia',   (-45.864, -67.500)),
    '011': ('Concordia',            (-31.393, -58.021)),
    '012': ('Córdoba',              (-31.417, -64.183)),
    '013': ('Corrientes',           (-27.467, -58.833)),
    '014': ('Cruz Alta',            (-33.013, -61.814)),
    '016': ('Mendoza',              (-32.890, -68.845)),
    '017': ('Córdoba',              (-31.417, -64.183)),
    '018': ('Reconquista',          (-29.144, -59.646)),
    '019': ('Resistencia',          (-27.451, -58.986)),
    '020': ('Diamante',             (-32.074, -60.638)),
    '023': ('Esquel',               (-42.909, -71.320)),
    '024': ('Formosa',              (-26.180, -58.175)),
    '025': ('Goya',                 (-29.141, -59.263)),
    '026': ('Gualeguaychú',         (-33.011, -58.518)),
    '029': ('Iguazú',               (-25.588, -54.566)),
    '031': ('Jujuy',                (-24.185, -65.299)),
    '033': ('La Plata',             (-34.921, -57.954)),
    '034': ('La Quiaca',            (-22.103, -65.598)),
    '037': ('Mar del Plata',        (-38.005, -57.541)),
    '038': ('Mendoza',              (-32.890, -68.845)),
    '040': ('Necochea',             (-38.554, -58.739)),
    '041': ('Paraná',               (-31.733, -60.530)),
    '042': ('Paso de los Libres',   (-29.718, -57.090)),
    '045': ('Pocitos',              (-22.383, -63.692)),
    '046': ('Posadas',              (-27.367, -55.896)),
    '047': ('Pto. Madryn',          (-42.768, -65.038)),
    '048': ('Río Gallegos',         (-51.623, -69.216)),
    '049': ('Río Grande',           (-53.788, -67.707)),
    '052': ('Rosario',              (-32.946, -60.639)),
    '053': ('Salta',                (-24.783, -65.423)),
    '054': ('San Javier',           (-30.576, -59.944)),
    '055': ('San Juan',             (-31.537, -68.536)),
    '057': ('San Lorenzo',          (-32.744, -60.737)),
    '059': ('San Nicolás',          (-33.336, -60.209)),
    '060': ('San Pedro',            (-33.679, -59.666)),
    '062': ('Santa Fe',             (-31.620, -60.699)),
    '066': ('Tinogasta',            (-28.066, -67.567)),
    '067': ('Ushuaia',              (-54.801, -68.302)),
    '069': ('Villa Constitución',   (-33.227, -60.337)),
    '073': ('Ezeiza',               (-34.822, -58.535)),
    '074': ('Tucumán',              (-26.808, -65.218)),
    '075': ('Neuquén',              (-38.952, -68.059)),
    '076': ('Orán',                 (-23.135, -64.325)),
    '078': ('San Rafael',           (-34.617, -68.330)),
    '079': ('La Rioja',             (-29.413, -66.855)),
    '080': ('San Antonio Oeste',    (-40.731, -65.011)),
    '082': ('Bernardo de Irigoyen', (-26.291, -53.650)),
    '083': ('San Luis',             (-33.295, -66.338)),
    '084': ('Santo Tomé',           (-28.546, -56.043)),
    '085': ('Villa Regina',         (-39.101, -67.075)),
    '086': ('Oberá',                (-27.487, -55.119)),
    '087': ('Caleta Olivia',        (-46.440, -67.526)),
    '088': ('General Deheza',       (-33.765, -63.787)),
    '089': ('Santiago del Estero',  (-27.794, -64.261)),
    '090': ('General Pico',         (-35.656, -63.757)),
    '091': ('Bs.As. Norte',         (-34.520, -58.479)),
    '092': ('Bs.As. Sur',           (-34.700, -58.400)),
    '099': ('Multiaduana',          (-34.603, -58.381)),
}

# COORDENADAS DE CIUDADES / PUNTOS DE EMBARQUE Y DESTINO
COORDS = {
    'OTROS ARGENTINA': (-34.603, -58.381),
    'BUENOS AIRES': (-34.603, -58.381),
    'MENDOZA': (-32.890, -68.845),
    'CORDOBA': (-31.417, -64.183),
    'ROSARIO': (-32.946, -60.639),
    'BAHIA BLANCA': (-38.719, -62.270),
    'MAR DEL PLATA': (-38.005, -57.541),
    'COMODORO RIVADAVIA': (-45.864, -67.500),
    'TUCUMAN': (-26.808, -65.218),
    'SALTA': (-24.783, -65.423),
    'NEUQUEN': (-38.952, -68.059),
    'SANTA FE': (-31.620, -60.699),
    'POSADAS': (-27.367, -55.896),
    'CORRIENTES': (-27.467, -58.833),
    'JUJUY': (-24.185, -65.299),
    'SAN FRANCISCO': (-31.425, -62.084),
    'TUCUMAN - COLOMBRES': (-26.578, -64.936),
    'SALTA - TABACAL': (-23.246, -64.262),
    'SALTA - METAN VIEJO': (-25.498, -64.970),
    'SALTA - MOSCONI': (-22.614, -63.812),
    'SALTA - PICHANAL': (-23.322, -64.218),
    'SALTA - ROSARIO DE LA FRONTERA': (-25.803, -64.970),
    'SALTA - CERRILLOS': (-24.906, -65.486),
    'SALTA - CAMPO QUIJANO': (-24.909, -65.638),
    'SALTA - LAS LAJITAS': (-24.716, -63.481),
    'SALTA - CARBONCITO': (-22.860, -64.164),
    'JUJUY - PAMPA BLANCA': (-23.748, -65.397),
    'CORRIENTES - MERCEDES': (-29.182, -58.078),
    'CORRIENTES - PASO DE LOS LIBRES': (-29.718, -57.090),
    'MISIONES': (-27.367, -55.896),
    'MISIONES - SANTO PIPO': (-27.091, -55.431),
    'MISIONES - APOSTOLES': (-27.918, -55.758),
    'MISIONES - SANTA ANA': (-27.368, -55.577),
    'ENTRE RIOS': (-31.733, -60.530),
    'ENTRE RIOS - VILLA ELISA': (-32.169, -58.397),
    'ENTRE RIOS - CONCEPCION DEL URUGUAY': (-32.482, -58.238),
    'ENTRE RIOS - SAN SALVADOR': (-31.619, -58.503),
    'ENTRE RIOS - GUALEGUAYCHU': (-33.011, -58.518),
    'ENTRE RIOS - CRESPO': (-32.028, -60.311),
    'ENTRE RIOS - CHAJARI': (-30.760, -57.980),
    'ENTRE RIOS - CONCORDIA': (-31.393, -58.021),
    'ENTRE RIOS - NOGOYÁ': (-32.394, -59.793),
    'ENTRE RIOS - PARANA': (-31.733, -60.530),
    'SANTA FE - ROSARIO': (-32.946, -60.639),
    'SANTA FE - SAN JERONIMO SUD': (-32.695, -60.943),
    'SANTA FE - FRANCK': (-31.583, -61.284),
    'SANTA FE - RAFAELA': (-31.252, -61.487),
    'SANTA FE - FRONTERA': (-31.069, -61.521),
    'SANTA FE - ESPERANZA': (-31.447, -60.931),
    'SANTA FE - BELLA ITALIA': (-29.551, -60.663),
    'SANTA FE - CORONDA': (-31.974, -60.921),
    'SANTA FE - RECREO': (-31.485, -60.735),
    'SANTA FE - CARCARAÑA': (-32.856, -61.153),
    'SANTE FE - AREQUITO': (-33.143, -61.465),
    'CORDOBA - GRAL DEHEZA': (-33.765, -63.787),
    'CORDOBA - PORTEÑA': (-30.872, -62.005),
    'CORDOBA - GRAL CABRERA': (-32.808, -63.878),
    'CORDOBA - EL TIO': (-30.363, -62.583),
    'CORDOBA - TIO PUJIO': (-32.309, -63.320),
    'CORDOBA - VILLA MARIA': (-32.407, -63.238),
    'CORDOBA - ALEJANDRO ROCA': (-33.358, -63.723),
    'CORDOBA - RIO CUARTO': (-33.131, -64.349),
    'CORDOBA - MONTE CRISTO': (-31.345, -63.945),
    'CORDOBA - MORTEROS': (-30.707, -62.000),
    'CORDOBA - SANTA ROSA DE CALAMUCHITA': (-32.069, -64.540),
    'CORDOBA - PILAR': (-31.682, -63.879),
    'CORDOBA - TANCACHA': (-32.239, -63.953),
    'CORDOBA - HERNANDO': (-32.426, -63.729),
    'CORDOBA - CHALACEA': (-30.964, -63.561),
    'CORDOBA - JUAREZ CELMAN': (-33.040, -63.430),
    'CORDOBA - TICINO': (-33.060, -62.890),
    'BUENOS AIRES - BARADERO': (-33.808, -59.510),
    'BUENOS AIRES - MAR DEL PLATA': (-38.005, -57.541),
    'BUENOS AIRES - EZEIZA': (-34.822, -58.535),
    'BUENOS AIRES - BUENOS AIRES': (-34.603, -58.381),
    'BUENOS AIRES - CHACABUCO': (-34.642, -60.474),
    'BUENOS AIRES - EL TALAR PACHECO': (-34.462, -58.641),
    'BUENOS AIRES - PILAR': (-34.459, -58.915),
    'BUENOS AIRES - LANUS': (-34.701, -58.394),
    'BUENOS AIRES - ZARATE': (-34.101, -59.028),
    'BUENOS AIRES - AVELLANEDA': (-34.665, -58.368),
    'BUENOS AIRES - ESCOBAR': (-34.346, -58.796),
    'BUENOS AIRES - 9 DE JULIO': (-35.444, -60.882),
    'BUENOS AIRES - TRES ARROYOS': (-38.376, -60.275),
    'BUENOS AIRES - SAN PEDRO': (-33.679, -59.666),
    'BUENOS AIRES - BERAZATEGUI': (-34.762, -58.211),
    'BUENOS AIRES - TORTUGUITAS': (-34.428, -58.748),
    'BUENOS AIRES - BURZACO': (-34.831, -58.391),
    'BUENOS AIRES - LINCOLN': (-34.865, -61.527),
    'BUENOS AIRES - CAMPANA': (-34.163, -58.959),
    'BUENOS AIRES - LA PLATA': (-34.921, -57.954),
    'BUENOS AIRES - LOS CARDALES': (-34.332, -59.115),
    'BUENOS AIRES - PEHUAJO': (-35.810, -61.893),
    'BUENOS AIRES - ENSENADA': (-34.866, -57.908),
    'MENDOZA - LUJAN DE CUYO': (-33.072, -68.878),
    'MENDOZA - SAN RAFAEL': (-34.617, -68.330),
    'MENDOZA - TUNUYAN': (-33.578, -69.020),
    'MENDOZA - GRAL ALVEAR': (-34.978, -67.715),
    'SAN LUIS': (-33.295, -66.338),
    'SAN LUIS - ARGENTINA': (-33.295, -66.338),
    'SAN JUAN': (-31.537, -68.536),
    'SAN JUAN - CHIMBAS': (-31.459, -68.551),
    'LA RIOJA': (-29.413, -66.855),
    'LA RIOJA - ANGUINAN': (-29.272, -67.812),
    'RIO NEGRO - VIEDMA': (-40.812, -62.997),
    'CATAMARCA': (-28.469, -65.779),
    # Chile — destinos y orígenes
    'CLP - SANTIAGO': (-33.459, -70.648),
    'CLP - RANCAGUA': (-34.170, -70.741),
    'CLP - PUNTA ARENAS': (-53.163, -70.917),
    'CLP - OSORNO': (-40.573, -73.136),
    'CLP - CODEGUA': (-34.032, -70.682),
    'CLP - PUERTO SAN ANTONIO': (-33.593, -71.621),
    'CLP - SAN ANTONIO': (-33.593, -71.621),
    'CLP - PLACILLA': (-34.088, -70.693),
    'CLP - VALPARAISO': (-33.047, -71.619),
    'CLP - MOLINA': (-35.114, -71.283),
    'CLP - ILLAPEL': (-31.638, -71.163),
    'CLP - CURICO': (-34.985, -71.239),
    'CLP - LOS ANGELES': (-37.470, -72.354),
    'CLP - TALCA': (-35.426, -71.655),
    'CLP - CONCON': (-32.926, -71.527),
    'CLP - LA CALERA': (-32.786, -71.196),
    'CLP - TALAGANTE': (-33.666, -70.929),
    'CLP - LAMPA': (-33.281, -70.879),
    'CLP - TALCAHUANO': (-36.724, -73.115),
    'CLP - OHHIGNS': (-34.170, -70.741),
    'CLP - SAN FERNANDO': (-34.586, -70.993),
    'CLP - MARCHIGUE': (-34.395, -71.530),
    'CLP - PAINE': (-33.812, -70.739),
    'CLP - MALLOA': (-34.451, -70.955),
    'CLP - QUILLOTA': (-32.878, -71.248),
    'CLP - CASABLANCA': (-33.320, -71.420),
    'SANTIAGO': (-33.459, -70.648),
    'VALPARAISO': (-33.047, -71.613),
    'SAN ANTONIO': (-33.594, -71.607),
    'LOS ANDES': (-32.833, -70.600),
    'TALCAHUANO': (-36.724, -73.115),
    'OSORNO': (-40.573, -73.136),
    'ANTOFAGASTA': (-23.650, -70.400),
    'PUNTA ARENAS': (-53.163, -70.917),
    'PUERTO MONTT': (-41.472, -72.936),
    'ARICA': (-18.478, -70.322),
    'IQUIQUE': (-20.213, -70.152),
    'COYHAIQUE': (-45.571, -72.066),
    'METROPOLITANA': (-33.459, -70.648),
    'PUERTO AYSEN': (-45.401, -72.698),
    # Mercosur
    'BRA - SAO PABLO': (-23.550, -46.633),
    'BRA - PORTO ALEGRE': (-30.033, -51.230),
    'BRA - RIO DE JANEIRO': (-22.906, -43.173),
    'BRA - CAXIAS DO SUL': (-29.168, -51.179),
    'UY - URUGUAY': (-32.522, -55.765),
    'UY - MONTEVIDEO': (-34.901, -56.165),
    'PY - PARAGUAY': (-23.442, -58.444),
    'PY - CAPITAN MIRANDA': (-27.201, -55.811),
}

# Lista pre-ordenada por especificidad (más largas primero)
_SORTED_COORDS = sorted(COORDS.items(), key=lambda x: len(x[0]), reverse=True)

import re

def haversine_matrix(lat1, lon1, lat2, lon2):
    """Calcula distancia en km usando Haversine."""
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat/2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

def pasos_coinciden(paso1: str, paso2: str) -> bool:
    if not paso1 or not paso2:
        return True
    return paso1.strip().upper() == paso2.strip().upper()

def get_coords(name: str):
    """Resuelve coordenadas (lat, lon) mediante coincidencia exacta, prefijo o búsqueda de subcadena."""
    if not name or str(name).strip().lower() in ('nan', 'none', '', 'no disponible', 'desconocido'):
        return (None, None)
    clean = str(name).strip().upper()
    
    # 1. Código aduana directo (ej. '012', '088')
    if clean in ADUANAS:
        return ADUANAS[clean][1]
        
    # 2. Coincidencia directa exacta
    if clean in COORDS:
        return COORDS[clean]
        
    # 3. Remover prefijos comunes de país
    clean_stripped = re.sub(r'^(CLP|BRA|UY|PY)\s*-\s*', '', clean)
    if clean_stripped in COORDS:
        return COORDS[clean_stripped]
        
    # 4. Búsqueda por subcadena ordenada por especificidad (específicas primero)
    for k, v in _SORTED_COORDS:
        k_city = k.split(' - ')[-1] if ' - ' in k else k
        if k == clean or k == clean_stripped:
            return v
        if clean == k_city or clean_stripped == k_city:
            return v
        if k in clean or clean in k:
            return v
        if k_city in clean or clean in k_city:
            return v
            
    # 5. Búsqueda por coincidencia de nombre de ciudad en ADUANAS
    for code, (aduana_city, coords) in ADUANAS.items():
        ad_upper = aduana_city.upper()
        if ad_upper in clean or clean in ad_upper:
            return coords
            
    return (None, None)

def resolver_origen_impo(puerto: str = "", aduana_raw: str = "", doc_str: str = "") -> str:
    """
    Resuelve origen para importación argentina.
    Si el puerto de embarque es un paso fronterizo ('LOS LIBERTADORES', 'MENDOZA', etc.)
    o genérico ('OTROS ARGENTINA'), resuelve la aduana de origen real mediante los
    primeros 3 caracteres del documento aduanero.
    """
    p = (puerto or "").strip().upper()
    doc = str(doc_str or aduana_raw or "").strip()
    cod3 = doc[:3] if len(doc) >= 3 else None
    
    # Si el puerto declarado es un paso fronterizo de tránsito o genérico, resolver por aduana
    pasos_transito = ("LOS LIBERTADORES", "LIBERTADORES", "CRISTO REDENTOR", "OTROS ARGENTINA", "", "SIN INFORMACION", "NO DECLARADO", "—")
    if p in pasos_transito and cod3 and cod3 in ADUANAS:
        return ADUANAS[cod3][0].upper()
        
    if p and p not in pasos_transito:
        return p
        
    if cod3 and cod3 in ADUANAS:
        return ADUANAS[cod3][0].upper()
        
    return "OTROS ARGENTINA"

def resolver_destino_expo(aduana_raw: str, puerto_desembarque: str) -> str:
    """Resuelve destino para exportación chilena."""
    p = (puerto_desembarque or "").strip().upper()
    if p and p not in ("SIN INFORMACION", "NO DECLARADO", "—"):
        return p
    a = (aduana_raw or "").strip().upper()
    if a:
        return a
    return "SANTIAGO"

def check_mendoza_transit_disclaimer(dest_name: str, fuente: str = "EXPO") -> bool:
    """
    Detecta si el documento EXPO indica 'MENDOZA' como destino, 
    lo cual habitualmente corresponde a la aduana de cruce/ingreso y no al destino final.
    """
    if not dest_name:
        return False
    clean = dest_name.strip().upper()
    return "MENDOZA" in clean and (fuente.upper() == "EXPO" or "EXPO" in fuente.upper())

def check_camionera_mendocina_disclaimer(origin_name: str, dest_name: str) -> bool:
    """
    Detecta si la ruta corresponde a 'CAMIONERA MENDOCINA' (Hub o depósito transitorio).
    """
    o = (origin_name or "").strip().upper()
    d = (dest_name or "").strip().upper()
    return "CAMIONERA MENDOCINA" in o or "CAMIONERA MENDOCINA" in d
