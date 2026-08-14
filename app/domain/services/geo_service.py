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

# COORDENADAS DE CIUDADES / PUNTOS DE EMBARQUE
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
    'SANTIAGO': (-33.459, -70.648),
    'VALPARAISO': (-33.047, -71.613),
    'SAN ANTONIO': (-33.594, -71.607),
    'LOS ANDES': (-32.833, -70.600)
}

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
    if not name:
        return (None, None)
    clean = name.strip().upper()
    for k, v in COORDS.items():
        if k in clean:
            return v
    return (None, None)

def resolver_origen_impo(puerto: str = "", aduana_raw: str = "", doc_str: str = "") -> str:
    """Resuelve origen para importación argentina."""
    p = (puerto or "").strip().upper()
    if p and p not in ("SIN INFORMACION", "NO DECLARADO", "—"):
        return p
    doc = str(doc_str or aduana_raw or "").strip()
    if len(doc) >= 3:
        code = doc[:3]
        if code in ADUANAS:
            return ADUANAS[code][0].upper()
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
