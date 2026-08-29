"""
Mercotruck — Buscador de Clientes Potenciales  v5.3 (Render-ready)
===================================================================
Cambios v5.3:
  - Columna "Dif %" separada de "Tarifa Merc." (ambas ordenables)
  - Filtro de categoría como desplegable (cargado desde /api/categorias)
Cambios Render-ready (sobre v5.1):
  - Rutas de datos relativas al proyecto (ya no hardcodeadas a C:\\...)
  - Variables de entorno para configuración opcional
  - Compatible con gunicorn (servidor de producción)
  - Puerto dinámico para Render (usa variable PORT)

Instalación local:
    pip install -r requirements.txt
    python app.py  →  http://localhost:5000

En Render:
    Se despliega automáticamente desde GitHub
"""

import os, io, csv, math, warnings
from datetime import datetime, date, timedelta
from flask import Flask, render_template_string, jsonify, request, Response
import pandas as pd
import numpy as np

warnings.filterwarnings('ignore')
app = Flask(__name__)

# ── CONFIGURACIÓN ─────────────────────────────────────────────────────────────
# En local: busca la carpeta "datos" dentro del mismo directorio que app.py
# En Render: también busca en "datos/" relativo al proyecto
BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DATA_FOLDER = os.environ.get('DATA_FOLDER', os.path.join(BASE_DIR, 'datos'))

HIST_FILE  = os.path.join(DATA_FOLDER, 'HISTORICO_MERCOTRUCK.xlsx')
IMPO_FILE  = os.path.join(DATA_FOLDER, 'SOFTTRADE_IMPO.xlsx')
EXPO_FILE  = os.path.join(DATA_FOLDER, 'SOFTTRADE_EXPO.xlsx')

FLETE_MIN     = int(os.environ.get('FLETE_MIN', 500))
FLETE_MAX     = int(os.environ.get('FLETE_MAX', 8000))
DOCS_MIN      = int(os.environ.get('DOCS_MIN', 5))
RADIO_KM      = int(os.environ.get('RADIO_KM', 100))
DIAS_RECIENTE = int(os.environ.get('DIAS_RECIENTE', 90))

# ── ENGINE DE LECTURA ─────────────────────────────────────────────────────────
def _get_engine():
    try:
        import python_calamine  # noqa
        return 'calamine'
    except ImportError:
        return 'openpyxl'

# ── ADUANAS ARGENTINAS ────────────────────────────────────────────────────────
ADUANAS = {
    '001':('001 - Bs.As. Capital',      (-34.603,-58.381)),
    '003':('003 - Bahía Blanca',        (-38.719,-62.270)),
    '004':('004 - Bahía Blanca',        (-38.719,-62.270)),
    '005':('005 - Barranqueras',        (-27.484,-58.941)),
    '006':('006 - Bs.As. (Ezeiza)',     (-34.822,-58.536)),
    '008':('008 - Córdoba',             (-31.417,-64.183)),
    '009':('009 - Corrientes',          (-27.467,-58.833)),
    '010':('010 - Entre Ríos',          (-31.733,-60.530)),
    '011':('011 - Formosa',             (-26.177,-58.174)),
    '012':('012 - Gral.Pico',           (-35.656,-63.757)),
    '013':('013 - Jujuy',               (-24.185,-65.299)),
    '014':('014 - La Pampa',            (-36.617,-64.283)),
    '015':('015 - La Rioja',            (-29.413,-66.856)),
    '016':('016 - Mar del Plata',       (-38.002,-57.558)),
    '017':('017 - Mendoza',             (-32.890,-68.845)),
    '018':('018 - Misiones',            (-27.367,-55.896)),
    '019':('019 - Neuquén',             (-38.952,-68.059)),
    '020':('020 - Posadas',             (-27.367,-55.896)),
    '021':('021 - Resistencia',         (-27.451,-58.987)),
    '022':('022 - Río Cuarto',          (-33.130,-64.350)),
    '023':('023 - Río Gallegos',        (-51.623,-69.218)),
    '024':('024 - Rosario',             (-32.946,-60.639)),
    '025':('025 - Salta',               (-24.783,-65.423)),
    '026':('026 - San Juan',            (-31.537,-68.536)),
    '027':('027 - San Luis',            (-33.295,-66.338)),
    '028':('028 - Santa Fe',            (-31.620,-60.699)),
    '029':('029 - Santiago del Estero', (-27.783,-64.267)),
    '030':('030 - Tucumán',             (-26.808,-65.218)),
    '031':('031 - Mendoza (Acceso E)',  (-32.890,-68.845)),
    '033':('033 - Bs.As. (Retiro)',     (-34.591,-58.374)),
    '035':('035 - San Nicolás',         (-33.336,-60.212)),
    '036':('036 - Zárate',              (-34.100,-59.033)),
    '037':('037 - Campana',             (-34.164,-58.956)),
    '038':('038 - Pilar',               (-34.458,-58.914)),
    '039':('039 - Luján',               (-34.570,-59.108)),
    '040':('040 - Morón',               (-34.653,-58.620)),
    '041':('041 - San Martín',          (-34.576,-58.539)),
    '042':('042 - Quilmes',             (-34.721,-58.254)),
    '043':('043 - Avellaneda',          (-34.659,-58.368)),
    '044':('044 - Lomas de Zamora',     (-34.758,-58.402)),
    '045':('045 - La Matanza',          (-34.771,-58.604)),
    '046':('046 - Merlo',               (-34.669,-58.727)),
    '047':('047 - Moreno',              (-34.637,-58.790)),
    '048':('048 - Tres de Febrero',     (-34.606,-58.563)),
    '049':('049 - Lanús',               (-34.701,-58.394)),
    '050':('050 - Florencio Varela',    (-34.809,-58.279)),
    '051':('051 - Berazategui',         (-34.764,-58.210)),
}

DESTINOS_CHILE = {
    'ARICA':       (-18.478,-70.314), 'IQUIQUE':    (-20.213,-70.130),
    'ANTOFAGASTA': (-23.650,-70.399), 'COQUIMBO':   (-29.954,-71.339),
    'VALPARAISO':  (-33.047,-71.620), 'SANTIAGO':   (-33.459,-70.645),
    'RANCAGUA':    (-34.170,-70.740), 'TALCA':      (-35.426,-71.655),
    'CONCEPCION':  (-36.827,-73.050), 'TEMUCO':     (-38.739,-72.590),
    'VALDIVIA':    (-39.814,-73.246), 'PUERTO MONTT':(-41.469,-72.942),
    'SAN ANTONIO': (-33.594,-71.621), 'CALAMA':     (-22.466,-68.930),
    'TOCOPILLA':   (-22.091,-70.199), 'MEJILLONES':  (-23.097,-70.447),
    'TALCAHUANO':  (-36.716,-73.117), 'OSORNO':     (-40.573,-73.134),
    'ARICA ZONA FRANCA':(-18.478,-70.314),
}
DESTINOS_BRASIL = {
    'SAO PAULO':   (-23.550,-46.633), 'RIO DE JANEIRO':(-22.906,-43.172),
    'PORTO ALEGRE':(-30.033,-51.230), 'CURITIBA':    (-25.429,-49.271),
    'FLORIANOPOLIS':(-27.595,-48.548),'SANTOS':      (-23.961,-46.333),
    'CAMPINAS':    (-22.905,-47.061), 'PARANAGUA':   (-25.520,-48.509),
}
DESTINOS_URUGUAY = {
    'MONTEVIDEO':  (-34.901,-56.165), 'COLONIA':     (-34.462,-57.840),
    'SALTO':       (-31.383,-57.961), 'PAYSANDU':    (-32.321,-58.076),
    'MERCEDES':    (-33.253,-58.022),
}
DESTINOS_PARAGUAY = {
    'ASUNCION':    (-25.286,-57.647), 'CIUDAD DEL ESTE':(-25.509,-54.611),
    'ENCARNACION': (-27.330,-55.866),
}

ALL_DESTINOS = {}
for d in [DESTINOS_CHILE, DESTINOS_BRASIL, DESTINOS_URUGUAY, DESTINOS_PARAGUAY]:
    ALL_DESTINOS.update(d)

def _norm(s):
    if not isinstance(s, str): return ''
    import unicodedata
    s = unicodedata.normalize('NFD', s.upper().strip())
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')

def _coords_destino(nombre):
    n = _norm(nombre)
    for k, v in ALL_DESTINOS.items():
        if _norm(k) in n or n in _norm(k):
            return v
    return None

def _haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

def _calc_camiones(kg, bultos):
    try:
        kg = float(kg); bultos = int(bultos)
    except:
        return 1
    if kg <= 0: return 1
    if bultos > 0 and (kg / bultos) < 50:
        return math.ceil(kg / 28000)
    return math.ceil(kg / 28500)

# ── CARGA DE DATOS ────────────────────────────────────────────────────────────
_cache = {}

def _load_data():
    global _cache
    if _cache: return _cache

    engine = _get_engine()
    print(f"[Mercotruck] Cargando datos con engine: {engine}")
    print(f"[Mercotruck] Carpeta de datos: {DATA_FOLDER}")

    # ── Historial ─────────────────────────────────────────────────────────────
    print("[Mercotruck] Leyendo historial...")
    try:
        hist = pd.read_excel(HIST_FILE, engine=engine)
    except FileNotFoundError:
        print(f"[ERROR] No se encontró: {HIST_FILE}")
        _cache = {'rutas': [], 'clientes': {}}
        return _cache

    hist.columns = [str(c).strip().upper() for c in hist.columns]

    # Columnas esperadas: ORIGEN, ADUANA, DESTINO, VENTA, FECHA (u otras variantes)
    col_map = {}
    for col in hist.columns:
        cl = col.lower()
        if 'origen' in cl:        col_map['ORIGEN'] = col
        elif 'aduana' in cl:      col_map['ADUANA'] = col
        elif 'destino' in cl:     col_map['DESTINO'] = col
        elif 'venta' in cl:       col_map['VENTA'] = col
        elif 'fecha' in cl:       col_map['FECHA'] = col

    rutas = []
    for _, row in hist.iterrows():
        origen_str  = str(row.get(col_map.get('ORIGEN',''), '')).strip().upper()
        aduana_str  = str(row.get(col_map.get('ADUANA',''), '')).strip().upper()
        destino_str = str(row.get(col_map.get('DESTINO',''), '')).strip().upper()
        venta_val   = row.get(col_map.get('VENTA',''), 0)
        fecha_val   = row.get(col_map.get('FECHA',''), None)

        try: venta = float(str(venta_val).replace('$','').replace(' ','').replace(',','').strip())
        except: venta = 0

        if venta < FLETE_MIN or venta > FLETE_MAX: continue

        coords_origen  = None
        cod = str(origen_str)[:3]
        if cod in ADUANAS:
            coords_origen = ADUANAS[cod][1]
        coords_destino = _coords_destino(destino_str)
        if not coords_origen or not coords_destino: continue

        fecha_dt = None
        if pd.notna(fecha_val):
            try: fecha_dt = pd.to_datetime(fecha_val).date()
            except: pass

        rutas.append({
            'origen_str':  origen_str,
            'aduana_str':  aduana_str,
            'destino_str': destino_str,
            'venta':       venta,
            'fecha':       fecha_dt,
            'lat_o': coords_origen[0],  'lon_o': coords_origen[1],
            'lat_d': coords_destino[0], 'lon_d': coords_destino[1],
        })

    print(f"[Mercotruck] {len(rutas)} rutas válidas del historial")

    # ── Softtrade ─────────────────────────────────────────────────────────────
    print("[Mercotruck] Leyendo Softtrade...")
    clientes = {}

    for label, fpath in [('IMPO', IMPO_FILE), ('EXPO', EXPO_FILE)]:
        if not os.path.exists(fpath):
            print(f"[WARN] No encontrado: {fpath}")
            continue
        try:
            df = pd.read_excel(fpath, engine=engine)
        except Exception as e:
            print(f"[ERROR] {fpath}: {e}")
            continue

        df.columns = [str(c).strip().upper() for c in df.columns]

        # Detectar columnas clave automáticamente
        col_empresa = next((c for c in df.columns if 'EMPRESA' in c or 'RAZON' in c or 'IMPORTADOR' in c or 'EXPORTADOR' in c), None)
        col_doc     = next((c for c in df.columns if 'DOCUMENTO' in c or 'DOC' in c or 'DUA' in c or 'NUMERO' in c), None)
        col_kg      = next((c for c in df.columns if 'KG' in c or 'PESO' in c or 'KILO' in c), None)
        col_bultos  = next((c for c in df.columns if 'BULTO' in c or 'UNIDAD' in c or 'CANT' in c), None)
        col_destino = next((c for c in df.columns if 'DESTINO' in c or 'PUERTO' in c or 'CIUDAD' in c), None)
        col_fecha   = next((c for c in df.columns if 'FECHA' in c or 'DATE' in c), None)
        col_pais    = next((c for c in df.columns if 'PAIS' in c or 'COUNTRY' in c or 'PAÍS' in c), None)
        col_transp  = next((c for c in df.columns if 'TRANSPORT' in c or 'CARRIER' in c or 'CAMION' in c), None)
        col_flete   = next((c for c in df.columns if 'FLETE' in c or 'TARIFA' in c or 'PRECIO' in c), None)

        if not col_empresa or not col_doc:
            print(f"[WARN] {label}: no se encontraron columnas de empresa/documento. Columnas: {list(df.columns)}")
            continue

        # ── Procesamiento vectorizado ──────────────────────────────────────────
        # Limpiar y normalizar columnas clave de una vez
        df['_empresa'] = df[col_empresa].astype(str).str.strip()
        df = df[~df['_empresa'].str.lower().isin(['nan', '', 'none'])]

        df['_doc']    = df[col_doc].astype(str).str.strip() if col_doc else ''
        df['_dest']   = df[col_destino].astype(str).str.strip() if col_destino else ''
        df['_pais']   = df[col_pais].astype(str).str.strip().str.upper() if col_pais else ''
        df['_transp'] = df[col_transp].astype(str).str.strip() if col_transp else ''

        # KG vectorizado
        if col_kg:
            df['_kg'] = pd.to_numeric(df[col_kg].astype(str).str.replace(',','.', regex=False), errors='coerce').fillna(0)
        else:
            df['_kg'] = 0.0

        # Bultos vectorizado
        if col_bultos:
            df['_bultos'] = pd.to_numeric(df[col_bultos].astype(str).str.replace(',','.', regex=False), errors='coerce').fillna(0).astype(int)
        else:
            df['_bultos'] = 0

        # Flete vectorizado
        if col_flete:
            df['_flete'] = pd.to_numeric(
                df[col_flete].astype(str).str.replace('$','',regex=False).str.replace('USD','',regex=False)
                .str.replace(' ','',regex=False).str.replace(',','',regex=False).str.strip(),
                errors='coerce').fillna(0)
        else:
            df['_flete'] = 0.0

        # Fechas vectorizadas
        if col_fecha:
            df['_fecha'] = pd.to_datetime(df[col_fecha], errors='coerce')
        else:
            df['_fecha'] = pd.NaT

        # Código aduana desde primeros 3 chars del documento
        df['_cod'] = df['_doc'].str[:3]

        # Pre-calcular lookup de destinos (solo destinos únicos)
        destinos_unicos = df['_dest'].unique()
        destino_coords_map = {}
        for d in destinos_unicos:
            destino_coords_map[d] = _coords_destino(d)

        df['_coords_destino'] = df['_dest'].map(destino_coords_map)

        # Camiones vectorizado
        df['_camiones'] = df.apply(lambda r: _calc_camiones(r['_kg'], r['_bultos']), axis=1)

        print(f"[Mercotruck] {label}: {len(df)} filas procesadas")

        # Agrupar por empresa
        for _, row in df.iterrows():
            empresa   = row['_empresa']
            doc       = row['_doc']
            kg        = float(row['_kg'])
            bultos    = int(row['_bultos'])
            dest      = row['_dest']
            pais      = row['_pais']
            transp    = row['_transp']
            flete_num = float(row['_flete'])
            camiones  = int(row['_camiones'])
            fecha_dt  = row['_fecha'].date() if pd.notna(row['_fecha']) else None
            cod       = row['_cod']

            coords_origen = ADUANAS.get(cod, (None, None))[1] if cod in ADUANAS else None
            origen_label  = ADUANAS.get(cod, (f'Aduana {cod}', None))[0] if cod else 'Desconocido'
            coords_destino = row['_coords_destino']

            clave = empresa.upper()
            if clave not in clientes:
                clientes[clave] = {
                    'empresa': empresa, 'tipo': label,
                    'pais': pais, 'destino_principal': dest,
                    'transportistas': set(), 'fletes_competencia': [],
                    'documentos': [], 'total_kg': 0, 'total_camiones': 0,
                    'fechas': [], 'coords_origen': coords_origen,
                    'coords_destino': coords_destino, 'origen_label': origen_label,
                }
            c = clientes[clave]
            c['total_kg']       += kg
            c['total_camiones'] += camiones
            c['documentos'].append({
                'doc': doc, 'kg': kg, 'bultos': bultos,
                'camiones': camiones, 'fecha': fecha_dt,
                'destino': dest, 'transportista': transp, 'flete': flete_num,
            })
            if transp and transp not in ('nan',''):  c['transportistas'].add(transp)
            if flete_num > 0:  c['fletes_competencia'].append(flete_num)
            if fecha_dt:       c['fechas'].append(fecha_dt)
            if not c['coords_origen'] and coords_origen:
                c['coords_origen'] = coords_origen; c['origen_label'] = origen_label
            if not c['coords_destino'] and coords_destino:
                c['coords_destino'] = coords_destino

    # Convertir sets a listas
    for c in clientes.values():
        c['transportistas'] = list(c['transportistas'])

    print(f"[Mercotruck] {len(clientes)} clientes únicos en Softtrade")

    # Extraer categorías únicas de destino para el desplegable
    categorias = sorted(set(
        c['destino_principal'] for c in clientes.values()
        if c.get('destino_principal') and c['destino_principal'].strip()
    ))

    _cache = {'rutas': rutas, 'clientes': clientes, 'categorias': categorias}
    return _cache

# ── MATCHING ──────────────────────────────────────────────────────────────────
def _match(cliente):
    data  = _load_data()
    rutas = data['rutas']
    if not rutas: return []

    co = cliente.get('coords_origen')
    cd = cliente.get('coords_destino')
    if not co or not cd: return []

    lat_o, lon_o = co; lat_d, lon_d = cd
    resultados = []

    for r in rutas:
        dist_o = _haversine(lat_o, lon_o, r['lat_o'], r['lon_o'])
        dist_d = _haversine(lat_d, lon_d, r['lat_d'], r['lon_d'])
        score  = 0
        if dist_o <= RADIO_KM: score += 2
        if dist_d <= RADIO_KM: score += 2
        if score >= 2:
            tipo = 'EXACTO' if score >= 4 else 'CERCANO'
            resultados.append({**r, 'score': score, 'tipo': tipo,
                                'dist_origen': round(dist_o,1),
                                'dist_destino': round(dist_d,1)})

    resultados.sort(key=lambda x: -x['score'])
    return resultados[:10]

# ── API ───────────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/clientes')
def api_clientes():
    data     = _load_data()
    clientes = data['clientes']
    pais_f   = request.args.get('pais','').upper()
    hoy      = date.today()

    resultado = []
    for clave, c in clientes.items():
        if len(c['documentos']) < DOCS_MIN: continue
        if pais_f and pais_f not in c['pais'].upper(): continue

        matches       = _match(c)
        if not matches: continue

        tipo_match    = matches[0]['tipo']
        ventas_merc   = [m['venta'] for m in matches]
        tarifa_merc   = round(sum(ventas_merc)/len(ventas_merc), 0) if ventas_merc else 0
        fletes_comp   = c['fletes_competencia']
        tarifa_comp   = round(sum(fletes_comp)/len(fletes_comp), 0) if fletes_comp else 0
        diff_pct      = round((tarifa_merc - tarifa_comp)/tarifa_comp*100, 1) if tarifa_comp else None

        ultima_fecha  = max(c['fechas']) if c['fechas'] else None
        dias_inactivo = (hoy - ultima_fecha).days if ultima_fecha else None

        resultado.append({
            'empresa':       c['empresa'],
            'tipo':          c['tipo'],
            'pais':          c['pais'],
            'destino':       c['destino_principal'],
            'origen':        c['origen_label'],
            'n_docs':        len(c['documentos']),
            'total_kg':      round(c['total_kg'], 0),
            'total_camiones':c['total_camiones'],
            'transportistas':c['transportistas'][:3],
            'tarifa_comp':   tarifa_comp,
            'tarifa_merc':   tarifa_merc,
            'diff_pct':      diff_pct,
            'tipo_match':    tipo_match,
            'ultima_fecha':  str(ultima_fecha) if ultima_fecha else None,
            'dias_inactivo': dias_inactivo,
            'documentos':    c['documentos'][:20],
        })

    resultado.sort(key=lambda x: (0 if x['tipo_match']=='EXACTO' else 1, x['empresa']))
    return jsonify(resultado)

@app.route('/api/categorias')
def api_categorias():
    data = _load_data()
    return jsonify({'categorias': data.get('categorias', [])})

@app.route('/api/exportar')
def api_exportar():
    data = _load_data()
    clientes = data['clientes']
    hoy = date.today()
    rows = []
    for c in clientes.values():
        if len(c['documentos']) < DOCS_MIN: continue
        matches = _match(c)
        if not matches: continue
        ventas = [m['venta'] for m in matches]
        tarifa_merc = round(sum(ventas)/len(ventas),0) if ventas else 0
        fletes = c['fletes_competencia']
        tarifa_comp = round(sum(fletes)/len(fletes),0) if fletes else 0
        ultima = max(c['fechas']) if c['fechas'] else None
        dias = (hoy - ultima).days if ultima else None
        rows.append({
            'Empresa': c['empresa'], 'País': c['pais'],
            'Destino': c['destino_principal'], 'Origen': c['origen_label'],
            'N° Docs': len(c['documentos']),
            'Total KG': c['total_kg'], 'Camiones Est.': c['total_camiones'],
            'Transportistas': ', '.join(c['transportistas'][:3]),
            'Tarifa Competencia USD': tarifa_comp, 'Tarifa Mercotruck USD': tarifa_merc,
            'Diferencia %': f"{'+' if tarifa_merc>tarifa_comp else ''}{round((tarifa_merc-tarifa_comp)/tarifa_comp*100,1)}%" if tarifa_comp else '',
            'Tipo Match': matches[0]['tipo'],
            'Última Actividad': str(ultima) if ultima else '',
            'Días Inactivo': dias,
        })
    output = io.StringIO()
    if rows:
        w = csv.DictWriter(output, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    return Response(output.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=mercotruck_leads.csv'})

@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'data_folder': DATA_FOLDER,
                    'hist_exists': os.path.exists(HIST_FILE),
                    'impo_exists': os.path.exists(IMPO_FILE),
                    'expo_exists': os.path.exists(EXPO_FILE)})

# ── HTML TEMPLATE ─────────────────────────────────────────────────────────────
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Mercotruck — Clientes Potenciales</title>
<style>
  :root {
    --navy:  #0D1117;
    --teal:  #1B5E6B;
    --teal2: #2980A0;
    --red:   #C0392B;
    --bg:    #F4F6F8;
    --card:  #FFFFFF;
    --text:  #1A1A2E;
    --muted: #6B7280;
    --green: #27AE60;
    --amber: #F39C12;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg); color: var(--text); }

  header {
    background: var(--navy);
    color: white;
    padding: 14px 28px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 2px 8px rgba(0,0,0,.4);
  }
  header h1 { font-size: 1.3rem; letter-spacing: 1px; }
  header span { font-size: .85rem; color: #94A3B8; }

  .toolbar {
    background: var(--teal);
    padding: 12px 28px;
    display: flex;
    gap: 12px;
    align-items: center;
    flex-wrap: wrap;
  }
  .toolbar select, .toolbar input, .toolbar button {
    padding: 7px 14px; border-radius: 6px; border: none;
    font-size: .9rem; cursor: pointer;
  }
  .toolbar select, .toolbar input { background: white; color: var(--text); min-width: 140px; }
  .btn-export { background: var(--red); color: white; font-weight: 600; }
  .btn-export:hover { background: #A93226; }
  .btn-buscar { background: white; color: var(--teal); font-weight: 700; }

  .stats-bar {
    padding: 10px 28px;
    background: #E8EEF3;
    font-size: .85rem;
    color: var(--muted);
    border-bottom: 1px solid #D1D9E0;
  }
  .stats-bar b { color: var(--teal); }

  .container { padding: 20px 28px; }

  .loading { text-align: center; padding: 60px; color: var(--muted); font-size: 1.1rem; }
  .spinner { width: 40px; height: 40px; border: 4px solid #ddd; border-top-color: var(--teal);
             border-radius: 50%; animation: spin .8s linear infinite; margin: 0 auto 16px; }
  @keyframes spin { to { transform: rotate(360deg); } }

  table { width: 100%; border-collapse: collapse; font-size: .88rem; }
  thead th {
    background: var(--navy); color: white;
    padding: 10px 12px; text-align: left;
    cursor: pointer; user-select: none;
    white-space: nowrap;
  }
  thead th:hover { background: var(--teal); }
  tbody tr { background: var(--card); border-bottom: 1px solid #E5E7EB; transition: background .15s; }
  tbody tr:hover { background: #EBF4F7; }
  td { padding: 9px 12px; vertical-align: middle; }

  .badge {
    display: inline-block; padding: 3px 9px; border-radius: 12px;
    font-size: .78rem; font-weight: 700; white-space: nowrap;
  }
  .badge-exacto  { background: #D1FAE5; color: #065F46; }
  .badge-cercano { background: #FEF3C7; color: #92400E; }
  .badge-impo    { background: #DBEAFE; color: #1E40AF; }
  .badge-expo    { background: #F3E8FF; color: #6B21A8; }

  .recency-green  { color: var(--green); font-weight: 700; }
  .recency-amber  { color: var(--amber); font-weight: 700; }
  .recency-red    { color: var(--red); font-weight: 700; }

  .diff-pos { color: var(--red); font-weight: 700; }
  .diff-neg { color: var(--green); font-weight: 700; }

  .btn-expand {
    background: var(--teal); color: white; border: none;
    padding: 4px 10px; border-radius: 4px; cursor: pointer; font-size: .8rem;
  }
  .btn-expand:hover { background: var(--teal2); }

  .detail-row td {
    padding: 0;
    background: #F8FAFC;
  }
  .detail-inner {
    padding: 12px 24px;
    display: none;
  }
  .detail-inner.open { display: block; }
  .detail-inner table { font-size: .82rem; }
  .detail-inner thead th { background: var(--teal); font-size: .82rem; }

  .call-card {
    background: linear-gradient(135deg, var(--navy) 0%, var(--teal) 100%);
    color: white; border-radius: 10px; padding: 18px 22px; margin-top: 10px;
  }
  .call-card h4 { font-size: .95rem; margin-bottom: 8px; opacity: .85; }
  .call-card p  { font-size: .9rem; line-height: 1.6; }

  .error-box {
    background: #FEE2E2; border: 1px solid #F87171;
    border-radius: 8px; padding: 20px; margin: 20px 0; color: #991B1B;
  }
</style>
</head>
<body>

<header>
  <h1>🚛 Mercotruck — Clientes Potenciales</h1>
  <span id="ts"></span>
</header>

<div class="toolbar">
  <select id="filtroPais">
    <option value="">🌎 Todos los países</option>
    <option value="CHILE">🇨🇱 Chile</option>
    <option value="BRASIL">🇧🇷 Brasil</option>
    <option value="URUGUAY">🇺🇾 Uruguay</option>
    <option value="PARAGUAY">🇵🇾 Paraguay</option>
  </select>
  <select id="filtroMatch">
    <option value="">Todos los matches</option>
    <option value="EXACTO">⭐ Solo EXACTO</option>
    <option value="CERCANO">~ Solo CERCANO</option>
  </select>
  <select id="filtroCategoria">
    <option value="">📦 Todas las categorías</option>
  </select>
  <input type="text" id="busqueda" placeholder="🔍 Buscar empresa...">
  <button class="btn-buscar" onclick="cargar()">Buscar</button>
  <button class="btn-export" onclick="exportar()">⬇ Exportar CSV</button>
</div>

<div class="stats-bar" id="statsBar">Cargando datos...</div>

<div class="container">
  <div class="loading" id="loading">
    <div class="spinner"></div>
    Cargando base de datos... (primera carga puede demorar ~30 segundos)
  </div>
  <div id="errorBox" style="display:none" class="error-box"></div>
  <div id="tableWrapper" style="display:none">
    <table id="tabla">
      <thead>
        <tr>
          <th onclick="sortBy('empresa')">Empresa ↕</th>
          <th onclick="sortBy('pais')">País ↕</th>
          <th onclick="sortBy('destino')">Destino ↕</th>
          <th onclick="sortBy('origen')">Origen ↕</th>
          <th onclick="sortBy('n_docs')">Docs ↕</th>
          <th onclick="sortBy('total_camiones')">Camiones ↕</th>
          <th onclick="sortBy('tarifa_comp')">Tarifa Comp. ↕</th>
          <th onclick="sortBy('tarifa_merc')">Tarifa Merc. ↕</th>
          <th onclick="sortBy('diff_pct')">Dif % ↕</th>
          <th onclick="sortBy('tipo_match')">Match ↕</th>
          <th onclick="sortBy('dias_inactivo')">Actividad ↕</th>
          <th>Detalle</th>
        </tr>
      </thead>
      <tbody id="tbody"></tbody>
    </table>
  </div>
</div>

<script>
let _data = [], _sortCol = 'empresa', _sortAsc = true;

document.getElementById('ts').textContent = new Date().toLocaleString('es-AR');
document.getElementById('busqueda').addEventListener('keydown', e => { if(e.key==='Enter') cargar(); });

// Cargar categorías al iniciar
async function cargarCategorias() {
  try {
    const res = await fetch('/api/categorias');
    const data = await res.json();
    const sel = document.getElementById('filtroCategoria');
    (data.categorias || []).forEach(cat => {
      const opt = document.createElement('option');
      opt.value = cat; opt.textContent = cat;
      sel.appendChild(opt);
    });
  } catch(e) { console.warn('No se pudieron cargar categorías:', e); }
}
cargarCategorias();

async function cargar() {
  const pais  = document.getElementById('filtroPais').value;
  const match = document.getElementById('filtroMatch').value;
  const cat   = document.getElementById('filtroCategoria').value.toLowerCase().trim();
  const bus   = document.getElementById('busqueda').value.toLowerCase().trim();

  document.getElementById('loading').style.display    = 'block';
  document.getElementById('tableWrapper').style.display = 'none';
  document.getElementById('errorBox').style.display   = 'none';
  document.getElementById('statsBar').textContent     = 'Consultando...';

  try {
    const url = '/api/clientes' + (pais ? '?pais='+pais : '');
    const res  = await fetch(url);
    if (!res.ok) throw new Error('HTTP ' + res.status);
    let data   = await res.json();

    if (match) data = data.filter(r => r.tipo_match === match);
    if (cat)   data = data.filter(r => (r.destino||'').toLowerCase().includes(cat));
    if (bus)   data = data.filter(r => r.empresa.toLowerCase().includes(bus));

    _data = data;
    _sortCol = 'empresa'; _sortAsc = true;
    renderTabla(data);

    const exactos  = data.filter(r=>r.tipo_match==='EXACTO').length;
    const cercanos = data.filter(r=>r.tipo_match==='CERCANO').length;
    document.getElementById('statsBar').innerHTML =
      `<b>${data.length}</b> clientes potenciales — <b>${exactos}</b> EXACTO · <b>${cercanos}</b> CERCANO`;
  } catch(e) {
    document.getElementById('loading').style.display = 'none';
    document.getElementById('errorBox').style.display = 'block';
    document.getElementById('errorBox').textContent = 'Error cargando datos: ' + e.message;
    document.getElementById('statsBar').textContent = 'Error';
  }
}

function renderTabla(data) {
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';

  data.forEach((r, i) => {
    const diffClass = r.diff_pct > 0 ? 'diff-pos' : 'diff-neg';
    const diffStr   = r.diff_pct != null
      ? `<span class="${diffClass}">${r.diff_pct > 0 ? '+' : ''}${r.diff_pct}%</span>` : '—';
    const tarComp  = r.tarifa_comp ? 'USD ' + r.tarifa_comp.toLocaleString() : '—';
    const tarMerc  = r.tarifa_merc ? 'USD ' + r.tarifa_merc.toLocaleString() : '—';

    let recClass = '', recStr = '—';
    if (r.dias_inactivo != null) {
      if (r.dias_inactivo < 60)       { recClass='recency-green'; recStr=r.dias_inactivo+'d'; }
      else if (r.dias_inactivo < 120) { recClass='recency-amber'; recStr=r.dias_inactivo+'d'; }
      else                             { recClass='recency-red';   recStr=r.dias_inactivo+'d'; }
    }

    const tipoMatch = r.tipo_match === 'EXACTO'
      ? '<span class="badge badge-exacto">⭐ EXACTO</span>'
      : '<span class="badge badge-cercano">~ CERCANO</span>';
    const tipoBadge = r.tipo === 'IMPO'
      ? '<span class="badge badge-impo">IMP</span>'
      : '<span class="badge badge-expo">EXP</span>';

    const trId   = 'row-' + i;
    const detId  = 'det-' + i;
    const innId  = 'inn-' + i;

    tbody.insertAdjacentHTML('beforeend', `
      <tr id="${trId}">
        <td>${tipoBadge} <b>${r.empresa}</b></td>
        <td>${r.pais || '—'}</td>
        <td>${r.destino || '—'}</td>
        <td style="font-size:.8rem;color:var(--muted)">${r.origen || '—'}</td>
        <td>${r.n_docs}</td>
        <td>${r.total_camiones}</td>
        <td>${tarComp}</td>
        <td>${tarMerc}</td>
        <td>${diffStr}</td>
        <td>${tipoMatch}</td>
        <td class="${recClass}">${recStr}</td>
        <td><button class="btn-expand" onclick="toggleDetalle('${detId}','${innId}')">▼ Ver</button></td>
      </tr>
      <tr class="detail-row" id="${detId}">
        <td colspan="12">
          <div class="detail-inner" id="${innId}">
            ${buildDetalle(r)}
          </div>
        </td>
      </tr>
    `);
  });

  document.getElementById('loading').style.display    = 'none';
  document.getElementById('tableWrapper').style.display = 'block';
}

function toggleDetalle(detId, innId) {
  const inner = document.getElementById(innId);
  const btn   = inner.closest('tr').previousElementSibling.querySelector('.btn-expand');
  if (inner.classList.contains('open')) {
    inner.classList.remove('open'); btn.textContent = '▼ Ver';
  } else {
    inner.classList.add('open'); btn.textContent = '▲ Cerrar';
  }
}

function buildDetalle(r) {
  const transp = r.transportistas && r.transportistas.length
    ? r.transportistas.join(', ') : 'No registrado';

  let docsHtml = '';
  if (r.documentos && r.documentos.length) {
    docsHtml = `
    <table style="width:100%;margin-top:10px">
      <thead><tr>
        <th>Documento</th><th>KG</th><th>Bultos</th>
        <th>Camiones</th><th>Flete Comp.</th><th>Fecha</th><th>Transportista</th>
      </tr></thead>
      <tbody>
        ${r.documentos.map(d=>`
          <tr>
            <td>${d.doc||'—'}</td>
            <td>${(d.kg||0).toLocaleString()}</td>
            <td>${d.bultos||0}</td>
            <td>${d.camiones||1}</td>
            <td>${d.flete?'USD '+d.flete:'—'}</td>
            <td>${d.fecha||'—'}</td>
            <td>${d.transportista||'—'}</td>
          </tr>`).join('')}
      </tbody>
    </table>`;
  }

  const diff = r.diff_pct != null
    ? (r.diff_pct > 0
        ? `Mercotruck es <b>USD ${Math.abs(r.tarifa_merc-r.tarifa_comp).toFixed(0)} más caro</b> que la competencia (${r.diff_pct}%). Destacar valor diferencial: servicio, tracking, seguro.`
        : `Mercotruck es <b>USD ${Math.abs(r.tarifa_merc-r.tarifa_comp).toFixed(0)} más económico</b> que lo que pagan (${Math.abs(r.diff_pct)}% de ahorro). ¡Argumento de venta directo!`)
    : 'Sin datos de tarifa comparativa.';

  return `
    <p style="font-size:.85rem;color:#444;margin-bottom:8px">
      <b>Transportistas actuales:</b> ${transp} &nbsp;|&nbsp;
      <b>Total KG:</b> ${(r.total_kg||0).toLocaleString()} &nbsp;|&nbsp;
      <b>Camiones estimados:</b> ${r.total_camiones}
    </p>
    ${docsHtml}
    <div class="call-card" style="margin-top:12px">
      <h4>📞 Script de llamada sugerido</h4>
      <p>
        "Hola, ¿hablo con el área de logística de <b>${r.empresa}</b>? 
        Soy [nombre] de <b>Mercotruck Internacional</b>. 
        Los contactamos porque vemos que realizan importaciones 
        ${r.destino ? 'desde ' + r.destino : ''} regularmente — 
        estamos operando esa misma ruta y me gustaría presentarles nuestra propuesta.<br><br>
        ${diff}"
      </p>
    </div>
  `;
}

function sortBy(col) {
  if (_sortCol === col) _sortAsc = !_sortAsc;
  else { _sortCol = col; _sortAsc = true; }
  const sorted = [..._data].sort((a,b) => {
    let va = a[col], vb = b[col];
    if (va == null) va = _sortAsc ? Infinity : -Infinity;
    if (vb == null) vb = _sortAsc ? Infinity : -Infinity;
    if (typeof va === 'string') return _sortAsc ? va.localeCompare(vb) : vb.localeCompare(va);
    return _sortAsc ? va - vb : vb - va;
  });
  renderTabla(sorted);
}

function exportar() { window.location = '/api/exportar'; }

cargar();
</script>
</body>
</html>
"""

# ── ENTRY POINT ───────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'false').lower() == 'true'
    print(f"[Mercotruck] Iniciando en puerto {port}")
    app.run(host='0.0.0.0', port=port, debug=debug)
