import re
import unicodedata
from typing import List, Tuple, Optional, Dict

def strip_accents(text: str) -> str:
    """Normaliza texto eliminando acentos (ASCII folding) y caracteres de control."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', str(text))
    return "".join(c for c in nfkd if not unicodedata.combining(c)).upper().strip()

def clean_product_name(raw_name: Optional[str]) -> str:
    """
    Extrae el nombre limpio y consolidado de un producto aduanero a partir de la
    descripción cruda de Softtrade / DUA.
    
    Ejemplos:
      '(8PK1435   ~ CORREAS DE TRANSMISION~ DAYCO~ M'  -> 'CORREAS DE TRANSMISION'
      '000000218121 ~SOLVENTE X-DSP 60/90'              -> 'SOLVENTE X-DSP 60/90'
      '0000374271 ~POLIETILENO~DOW~INDUSTRIAL~BOLSAS'  -> 'POLIETILENO'
      '0001 ~ ACEITE DE OLIVA'                          -> 'ACEITE DE OLIVA'
      '0001 ~ HARINA DE SANGRE AVIAR~ YARUBA S'         -> 'HARINA DE SANGRE AVIAR'
      '0001 ~ HARINA DE SANGRE AVIAR~ YERUVA S'         -> 'HARINA DE SANGRE AVIAR'
      '0001CAL ~CAL VIVA(HIDRATADA)'                    -> 'CAL VIVA (HIDRATADA)'
      '001-SOJA ~SOJA DESACTIVADA'                      -> 'SOJA DESACTIVADA'
    """
    if not raw_name or str(raw_name).strip().lower() in ('nan', 'none', '', 'no disponible', 'n/d', 'sin datos'):
        return "MERCADERIA GENERAL"

    text = str(raw_name).strip()

    # Si contiene separadores aduaneros '~'
    if '~' in text:
        parts = [p.strip() for p in text.split('~') if p.strip()]
        
        # En la estructura aduanera, la parte 0 suele ser código/lote/item si contiene dígitos o es muy corta
        if len(parts) >= 2 and (re.search(r'\d', parts[0]) or len(parts[0]) <= 3 or parts[0].startswith('(')):
            candidate = parts[1]
        elif parts:
            candidate = parts[0]
        else:
            candidate = text
    else:
        # Si no tiene '~', remover prefijos numéricos de inicio tipo '0001 - ', '0001 ', '(8PK1435) '
        candidate = re.sub(r'^\(?\d+[\d\-_/\.A-Z]*\)?\s*[-:]?\s*', '', text)

    # Limpiar prefijos de código remanentes en el candidato (solo si inician con números o paréntesis numéricos)
    candidate = re.sub(r'^\(?\d+[\d\-_/\.]*\)?\s*', '', candidate)

    # Formatear paréntesis con espacios prolijos: ej. 'CAL VIVA(HIDRATADA)' -> 'CAL VIVA (HIDRATADA)'
    candidate = re.sub(r'\s*\(\s*', ' (', candidate)
    candidate = re.sub(r'\s*\)\s*', ') ', candidate)

    # Normalizar espacios múltiples y caracteres de relleno
    candidate = re.sub(r'\s+', ' ', candidate).strip(" ~-–_/*#")

    # Si tras la limpieza quedó vacío o muy corto, fallback a la descripción original
    if len(candidate) < 2:
        return text.upper().strip()

    return candidate.upper().strip()


# ── DEFINICIÓN MAESTRA DE CATEGORÍAS Y KEYWORDS ──────────────────────────────
# Agrupadas por dominio comercial. Se compilarán y ordenarán por longitud descendente
# de frase para que las más específicas ganen siempre sobre los unigramas genéricos.
CATEGORIAS_DEFINICION: List[Tuple[str, List[str]]] = [
    ('Alimentación animal', [
        'HARINA DE PESCADO', 'HARINA DE SANGRE AVIAR', 'HARINA DE SANGRE', 'HARINA DE CARNE',
        'HARINA DE HUESO', 'ALIMENTO PARA AVES', 'ALIMENTO PARA PECES', 'ALIMENTO GANADO',
        'ALIMENTO PARA MASCOTA', 'ALIMENTO PARA MASCOTAS', 'ALIMENTOS PARA MASCOTA',
        'ALIMENTOS PARA MASCOTAS', 'ALIMENTO PARA PERRO', 'ALIMENTO PARA PERROS',
        'ALIMENTOS PARA PERRO', 'ALIMENTOS PARA PERROS', 'ALIMENTO PARA GATO',
        'ALIMENTO PARA GATOS', 'ALIMENTOS PARA GATO', 'ALIMENTOS PARA GATOS',
        'ALIMENTOS PARA ANIMALES', 'ALIMENTOS PARA ANIMALE', 'PET FOOD',
        'COMIDA PARA PERRO', 'COMIDA PARA GATO', 'ALIMENTO BALANCEADO',
        'BALANCEADO', 'FORRAJE', 'SILO'
    ]),
    ('Carnes y derivados', [
        'CARNE DE VACUNO', 'CARNE BOVINA', 'CARNE DE POLLO', 'CARNE DE CERDO',
        'CARNE PORCINA', 'CARNE DE CORDERO', 'CARNE VACUNA', 'CARNE',
        'VACUNO', 'BOVINO', 'PORCINO', 'POLLO', 'CERDO', 'CORDERO',
        'FRIGORIF', 'EMBUTIDO', 'SALCHICHA', 'JAMON', 'FIAMBRE', 'VISCERA', 'MONDONGO'
    ]),
    ('Salmon y pesca', [
        'FILETE DE SALMON', 'FILETE DE TRUCHA', 'FILETE DE MERLUZA', 'FILETE DE PESCADO',
        'FILETE DE', 'SALMON', 'TRUCHA', 'MERLUZA', 'PESCADO', 'MARISCO', 'CALAMAR', 'ATUN'
    ]),
    ('Plásticos y polímeros', [
        'RESINA PLASTICA', 'POLIPROPILENO', 'POLIETILENO', 'POLIESTIRENO',
        'POLIVINILO', 'PVC', 'PLASTICO', 'POLIMERO', 'GRANULO'
    ]),
    ('Minerales y fertilizantes', [
        'CARBONATO DE CALCIO', 'CARBONATO', 'POLISULFURO DE CALCIO', 'POLISULFURO',
        'SULFATO DE COBRE', 'SULFATO', 'FOSFATO', 'NITRATO', 'UREA', 'FERTILIZANTE',
        'MINERAL', 'POTASIO', 'AZUFRE', 'SAL INDUSTRIAL'
    ]),
    ('Combustibles y gas', [
        'CARBON VEGETAL', 'CARBON DE LEÑA', 'CARBON COQUE', 'CARBON ACTIVADO',
        'GAS PROPANO', 'GAS BUTANO', 'GAS LICUADO', 'GLP', 'GNL',
        'COMBUSTIBLE', 'GASOIL', 'DIESEL', 'NAFTA', 'KEROSENE', 'COQUE', 'CARBON'
    ]),
    ('Aceites y grasas', [
        'ACIDO GRASO', 'ACEITE DE OLIVA', 'ACEITE DE GIRASOL', 'ACEITE DE SOJA',
        'ACEITE DE MAIZ', 'ACEITE VEGETAL', 'ACEITE REFINADO', 'ACEITE CRUDO',
        'MANTECA VEGETAL', 'MANTECA DE CERDO', 'ACEITE', 'GRASA', 'OLEINA',
        'SEBO', 'MARGARINA'
    ]),
    ('Lácteos', [
        'MANTECA DE LECHE', 'MANTEQUILLA', 'MANTECA', 'QUESO', 'LECHE',
        'YOGUR', 'CREMA DE LECHE', 'CREMA', 'SUERO DE LECHE', 'SUERO',
        'LACTEO', 'LACTOSUERO'
    ]),
    ('Azúcar y dulces', [
        'AZUCAR', 'GLUCOSA', 'FRUCTOSA', 'JARABE', 'CARAMELO', 'CHOCOLATE',
        'CACAO', 'DULCE DE LECHE', 'DULCE', 'MIEL', 'ALMIBAR', 'GALLETITA',
        'GALLETA', 'BIZCOCHO', 'ALFAJOR'
    ]),
    ('Cereales y harinas', [
        'HARINA DE TRIGO', 'HARINA DE MAIZ', 'HARINA DE SOJA', 'SOJA DESACTIVADA',
        'MAIZ', 'TRIGO', 'SOJA', 'ARROZ', 'HARINA', 'ALMIDON', 'FECULA',
        'CEREAL', 'GRANOLA', 'AVENA', 'CEBADA', 'SORGO', 'GIRASOL', 'MANI',
        'EXPELLER', 'PELLET', 'SEMILLA'
    ]),
    ('Frutas y verduras', [
        'PALTA', 'LIMON', 'UVA', 'CEREZA', 'KIWI', 'ARANDANO', 'MANZANA',
        'PERA', 'DURAZNO', 'CITRICO', 'FRUTA', 'VERDURA', 'TOMATE', 'PAPA',
        'CEBOLLA', 'AJO', 'LECHUGA', 'ESPINACA', 'ZAPALLO', 'BROCOLI',
        'FRAMBUESA', 'OREGANO', 'ESPECIA', 'LEGUMBRE'
    ]),
    ('Bebidas', [
        'VINO TINTO', 'VINO BLANCO', 'VINO', 'VINOS', 'CERVEZA', 'BEBIDA',
        'BEBIDAS', 'JUGO', 'NECTAR', 'GASEOSA', 'AGUA MINERAL', 'SPIRITS',
        'WHISKY', 'LICOR', 'SIDRA'
    ]),
    ('Tabaco', [
        'CIGARRILLO', 'CIGARRILLOS', 'TABACO', 'CIGARRO'
    ]),
    ('Pasta y panificados', [
        'PASTA ALIMENTICIA', 'FIDEOS', 'SPAGHETTI', 'TALLARINES',
        'PANIFICADO', 'PAN', 'TOSTADA'
    ]),
    ('Congelados y helados', [
        'HELADO', 'CONGELADO', 'PRECOCINADO', 'PAPAS PREFRITA', 'PAPAS PREPARA',
        'PIZZA', 'EMPANADA'
    ]),
    ('Yerba y infusiones', [
        'YERBA MATE', 'YERBA', 'MATE', 'TE', 'CAFE', 'INFUSION', 'HIERBA'
    ]),
    ('Químicos industriales', [
        'SOLVENTE', 'DISOLVENTE', 'ACIDO', 'RESINA', 'PIGMENTO', 'TINTA',
        'BARNIZ', 'PINTURA', 'BREA', 'ADITIVO', 'ANHIDRIDO', 'REACTIVO',
        'CATALIZADOR', 'BIOCIDA', 'FUNGICIDA', 'HERBICIDA', 'PESTICIDA'
    ]),
    ('Metales y siderurgia', [
        'ACERO', 'HIERRO', 'ALUMINIO', 'COBRE', 'ZINC', 'PLOMO',
        'ALAMBRE', 'ALAMBRON', 'CHAPA DE GRANITO', 'CHAPA', 'PLANCHA', 'TUBO',
        'CAÑO', 'PERFIL METALICO', 'BARRA DE', 'LINGOTE'
    ]),
    ('Papel y cartón', [
        'BALDE (RECIPIENTE) DE PAPEL', 'BALDE DE PAPEL', 'CAJA DE CARTON',
        'ENVASE DE CARTON', 'BOLSA DE PAPEL', 'PAPEL', 'CARTON',
        'CARTULINA', 'TISSUE', 'HIGIENICO'
    ]),
    ('Vidrio y cerámica', [
        'VIDRIO', 'CERAMICA', 'PORCELANA', 'LADRILLO', 'LADRILL',
        'BALDOSA', 'REVESTIMIENTO'
    ]),
    ('Madera y corcho', [
        'MADERA ASERRADA', 'TAPON DE CORCHO', 'MADERA', 'CORCHO', 'TRIPLAY', 'MDF'
    ]),
    ('Textil y calzado', [
        'PANTALON DE VESTIR', 'PANTALONES', 'PANTALON', 'CALCETINES', 'CALCETINE',
        'ZAPATILLA', 'ZAPATILLAS', 'CALZADO', 'ZAPATO', 'BOTA', 'BOTAS',
        'CAMISA', 'VESTIDO', 'ROPA', 'INDUMENTARIA', 'TELA', 'TEJIDO',
        'MEDIA', 'TEXTIL', 'HILO', 'LANA', 'FIBRA TEXTIL'
    ]),
    ('Envases y embalajes', [
        'BOTELLA', 'LATA', 'TARRO', 'TAMBOR', 'BIDON', 'SACHET',
        'BANDEJA', 'BOLSA', 'CONTENEDOR', 'EMBALAJE', 'ENVASE'
    ]),
    ('Vehículos y autopartes', [
        'CORREAS DE TRANSMISION', 'CORREA DE TRANSMISION', 'CORREA', 'CORREAS',
        'CAMIONETA', 'STATION WAGON', 'AUTOMOVIL', 'VEHICULO', 'AUTOPARTE',
        'REPUESTO', 'NEUMATICO', 'LLANTA', 'MOTOR AUTOMOTRIZ'
    ]),
    ('Materiales construcción', [
        'CAL VIVA (HIDRATADA)', 'CAL VIVA(HIDRATADA)', 'CAL HIDRATADA', 'CAL VIVA',
        'CAL', 'CEMENTO', 'YESO', 'ARENA', 'HORMIGON', 'AGREGADO',
        'AISLANTE', 'LANA DE VIDRIO', 'FIBRA DE VIDRIO'
    ]),
    ('Maquinaria y equipos', [
        'MAQUINARIA', 'EQUIPO', 'MOTOR', 'TURBINA', 'COMPRESOR',
        'BOMBA', 'VALVULA', 'ELECTRODOMESTICO', 'CALEFACTOR', 'GENERADOR'
    ]),
    ('Electrónica', [
        'ELECTRONICO', 'ELECTRONICA', 'CABLES', 'INTERRUPTOR', 'PILAS',
        'BATERIA', 'TRANSFORMADOR', 'CIRCUITO'
    ]),
    ('Farmacia y salud', [
        'FARMACO', 'MEDICAMENTO', 'CAPSULAS', 'AMPOLLA', 'COMPRIMIDO',
        'VACUNA', 'ANTIBIOTICO', 'VITAMINA', 'SUPLEMENTO', 'COSMETICO',
        'PERFUME', 'SHAMPOO', 'JABON', 'DETERGENTE', 'LIMPIEZA'
    ]),
]

# Construir lista aplanada compilada ordenada por longitud de frase descendente
# Cada elemento: (regex_pattern, category_name, raw_kw)
_COMPILED_RULES: List[Tuple[re.Pattern, str, str]] = []

seen_kws = set()
flat_rules = []
for cat_name, kws in CATEGORIAS_DEFINICION:
    for kw in kws:
        clean_kw = strip_accents(kw)
        if (clean_kw, cat_name) not in seen_kws:
            seen_kws.add((clean_kw, cat_name))
            flat_rules.append((clean_kw, cat_name))

# Ordenar por longitud de la palabra clave descendente (específicas primero)
flat_rules.sort(key=lambda x: len(x[0]), reverse=True)

for kw, cat in flat_rules:
    # Usar \b para coincidencia exacta de palabra y evitar colisiones como PAN -> PANTALON
    pattern = re.compile(rf'\b{re.escape(kw)}\b', re.IGNORECASE)
    _COMPILED_RULES.append((pattern, cat, kw))


def categorizar_mercaderia(nombre: Optional[str]) -> str:
    """
    Clasifica una descripción de mercadería aduanera en una de las macro-categorías.
    Utiliza coincidencia de palabras con límites de palabra (\b) y evaluación
    por prioridad de longitud de frase (específicas primero).
    """
    if not nombre or str(nombre).strip().lower() in ('nan', 'none', '', 'no disponible', 'n/d'):
        return 'Otros'

    texto_normalizado = strip_accents(str(nombre))

    for pattern, cat, _ in _COMPILED_RULES:
        if pattern.search(texto_normalizado):
            return cat

    return 'Otros'
