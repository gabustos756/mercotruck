# Mercotruck Prospector v5.3
## Documentación Completa de Cálculos, Lógicas y Validaciones

**Última actualización:** v5.3  
**Propósito:** Especificar cada columna, validación, cálculo y regla de lógica aplicada en la herramienta.

---

## 📋 Tabla de Contenidos

1. [Configuración y Constantes](#configuración-y-constantes)
2. [Flujo de Carga de Datos](#flujo-de-carga-de-datos)
3. [Direcciones y Rutas](#direcciones-y-rutas)
4. [Validaciones de Documentos](#validaciones-de-documentos)
5. [Cálculo de Camiones](#cálculo-de-camiones)
6. [Cálculo de Precios](#cálculo-de-precios)
7. [Diferencia Porcentual](#diferencia-porcentual)
8. [Geographic Matching](#geographic-matching)
9. [Score de Oportunidad](#score-de-oportunidad)
10. [Categorización de Mercaderías](#categorización-de-mercaderías)
11. [Historial de Precios](#historial-de-precios)
12. [Columnas del Resultado Final](#columnas-del-resultado-final)
13. [Filtros y Búsqueda](#filtros-y-búsqueda)

---

## Configuración y Constantes

### Archivos de Entrada

```
HIST_FILE  = HISTORICO_MERCOTRUCK.xlsx      → Historial interno de Mercotruck
IMPO_FILE  = SOFTTRADE_IMPO.xlsx            → Importaciones (Argentina → Chile)
EXPO_FILE  = SOFTTRADE_EXPO.xlsx            → Exportaciones (Chile → Argentina)
```

### Parámetros de Validación

| Constante | Valor | Significado |
|-----------|-------|-------------|
| `FLETE_MIN` | 500 USD | Precio mínimo válido por documento |
| `FLETE_MAX` | 8,000 USD | Precio máximo válido por documento |
| `DOCS_MIN` | 5 | Documentos mínimos para calificar como prospecto |
| `RADIO_EXACTO` | 50 km | Radio de distancia para match "EXACTO" |
| `RADIO_CERCANO` | 100 km | Radio de distancia para match "CERCANO" |
| `DIAS_RECIENTE` | 90 días | Ventana temporal para "precio reciente" |

---

## Flujo de Carga de Datos

### 1. Lectura de Archivos Excel

```python
# Motor seleccionado automáticamente:
# - Intenta calamine (más rápido)
# - Si no está disponible, usa openpyxl

engine = 'calamine' if python_calamine else 'openpyxl'
```

**Archivos leídos:**
- `HISTORICO_MERCOTRUCK.xlsx` → DataFrame `hist`
- `SOFTTRADE_IMPO.xlsx` → DataFrame `impo`
- `SOFTTRADE_EXPO.xlsx` → DataFrame `expo`

### 2. Normalización de Datos

**Todas las columnas de texto se convierten a mayúsculas y se trimean:**

```python
for col in df.columns:
    if df[col].dtype == object:
        df[col] = df[col].str.upper().str.strip()
```

---

## Direcciones y Rutas

### IMPO Direction (Argentina → Chile)

**Fuente de datos:** `SOFTTRADE_IMPO.xlsx`

**Mapeo de columnas:**

| Campo SOFTTRADE | Campo App | Descripción |
|-----------------|-----------|-------------|
| `Puerto de Embarque` | `origen` | Puerto de salida en Argentina |
| `Aduana` | `destino` | Aduana de llegada en Chile |
| (derivado) | `fuente` | Fijado como "IMPO" |
| (derivado) | `paso` | "Paso fronterizo" (siempre fijo) |

**Lógica:**
- Origen = Puerto de Embarque
- Destino = Aduana de Aduanas chilenas
- Paso = "Paso fronterizo" (constante)

**Ejemplo:**
```
Puerto Embarque: BUENOS AIRES
Aduana: ADUANAS CHILENAS
→ Ruta: BUENOS AIRES → ADUANAS CHILENAS (Paso fronterizo)
```

---

### EXPO Direction (Chile → Argentina)

**Fuente de datos:** `SOFTTRADE_EXPO.xlsx`

**Mapeo de columnas:**

| Campo SOFTTRADE | Campo App | Descripción |
|-----------------|-----------|-------------|
| `Aduana` | `origen` | Aduanas chilenas de origen |
| `Puerto de Desembarque` | `destino` | Puerto de llegada en Argentina |
| `DUA` | `doc_id` | Identificador único del documento |
| (derivado) | `fuente` | Fijado como "EXPO" |
| (derivado) | `paso` | "Paso fronterizo" (siempre fijo) |

**Lógica:**
- Origen = Aduana chilena
- Destino = Puerto de Desembarque argentino
- Paso = "Paso fronterizo" (constante)
- Documento identificador = DUA (único por registro)

**Ejemplo:**
```
Aduana: ADUANAS CHILENAS
Puerto Desembarque: BUENOS AIRES
DUA: 12345678
→ Ruta: ADUANAS CHILENAS → BUENOS AIRES (Paso fronterizo)
```

---

## Validaciones de Documentos

Antes de procesar cualquier documento, se aplican filtros de validación:

### Para IMPO

```python
# 1. Descartar estado que NO sea "EMBARQUE CONFIRMADO"
df = df[df['Estado Embarque'] == 'EMBARQUE CONFIRMADO']

# 2. Validar rango de flete
df = df[(df['Flete'] >= FLETE_MIN) & (df['Flete'] <= FLETE_MAX)]

# 3. Validar que exista empresa
df = df[df['Empresa'].notna()]

# 4. Validar que exista RUT
df = df[df['RUT'].notna()]

# 5. Validar que exista Puerto de Embarque
df = df[df['Puerto de Embarque'].notna()]

# 6. Validar que exista Aduana
df = df[df['Aduana'].notna()]
```

### Para EXPO

```python
# 1. Descartar estado que NO sea "EMBARQUE CONFIRMADO"
df = df[df['Estado Embarque'] == 'EMBARQUE CONFIRMADO']

# 2. Validar rango de flete
df = df[(df['Flete'] >= FLETE_MIN) & (df['Flete'] <= FLETE_MAX)]

# 3. Validar que exista empresa
df = df[df['Empresa'].notna()]

# 4. Validar que exista RUT
df = df[df['RUT'].notna()]

# 5. Validar que exista Aduana (Chile)
df = df[df['Aduana'].notna()]

# 6. Validar que exista Puerto de Desembarque
df = df[df['Puerto de Desembarque'].notna()]

# 7. Validar que exista DUA (identificador único)
df = df[df['DUA'].notna()]
```

**Criterio de calificación como prospecto:**
- Mínimo 5 documentos válidos por empresa
- Si una empresa tiene < 5 docs, es descartada

```python
# Contar documentos por empresa
doc_count = df.groupby('RUT').size()

# Filtrar solo empresas con >= 5 documentos
qualified_ruts = doc_count[doc_count >= DOCS_MIN].index
df = df[df['RUT'].isin(qualified_ruts)]
```

---

## Cálculo de Camiones

### Fórmula Base

```
Total Camiones = TECHO(Peso Total en kg / 28,500 kg)
```

Donde:
- **28,500 kg** = Capacidad máxima de un camión (constante fija)
- **TECHO** = Función ceiling/redondear hacia arriba

### Regla de Negocio

**No hay distinción por tipo de bulto o mercadería:**
- Independientemente del contenido, cada camión tiene techo de 28,500 kg
- Se aplica para ALL documentos en la agregación por empresa

### Ejemplo

| Peso Total (kg) | Cálculo | Camiones |
|-----------------|---------|----------|
| 10,000 | TECHO(10,000 / 28,500) | 1 |
| 28,500 | TECHO(28,500 / 28,500) | 1 |
| 28,501 | TECHO(28,501 / 28,500) | 2 |
| 57,000 | TECHO(57,000 / 28,500) | 2 |
| 85,500 | TECHO(85,500 / 28,500) | 3 |

### Implementación en Código

```python
import numpy as np

# Calcular camiones por documento
df['camiones'] = np.ceil(df['Peso (kg)'] / 28500).astype(int)

# Agregación por empresa: suma total de camiones
grupo = df.groupby(['RUT', 'Empresa', 'Origen', 'Destino']).agg({
    'camiones': 'sum'
}).reset_index()

grupo.rename(columns={'camiones': 'total_camiones'}, inplace=True)
```

---

## Cálculo de Precios

### Precio de Mercado (Promedio Softtrade)

Se calcula el promedio simple del flete reportado en Softtrade para cada documento de la empresa:

```python
# Por documento (sin agregar)
precio_documento = df['Flete']  # USD

# Promedio por empresa
precio_promedio_empresa = df.groupby('RUT')['Flete'].mean()

# Este valor se replica en cada fila para la empresa
df['flete_mercado'] = df['RUT'].map(precio_promedio_empresa)
```

**Regla:** Si no hay documentos válidos, no hay precio de mercado.

### Precio de Mercotruck (90 días reciente)

Se busca en el historial interno **documentos de viajes en los últimos 90 días** en esa ruta:

```python
# 1. Identificar la ruta (origen → destino)
ruta_empresa = f"{df['Origen']} → {df['Destino']}"

# 2. Filtrar historial por ruta
hist_ruta = hist[
    (hist['Origen'] == origen) & 
    (hist['Destino'] == destino)
]

# 3. Calcular fecha límite (90 días atrás)
fecha_limite = datetime.now() - timedelta(days=90)

# 4. Filtrar viajes recientes
hist_reciente = hist_ruta[hist_ruta['Fecha'] >= fecha_limite]

# 5. Calcular promedio de los últimos 90 días
flete_reciente = hist_reciente['Venta (USD)'].mean()

# Si no hay viajes en 90d, usar promedio histórico
if pd.isna(flete_reciente) or len(hist_reciente) == 0:
    flete_reciente = hist_ruta['Venta (USD)'].mean()
```

**Fallback:** 
- Si existen viajes en los últimos 90 días → usar promedio reciente
- Si no → usar promedio histórico
- Si no hay historial en la ruta → sin precio Mercotruck

### Precio por Camión

Ambos precios se expresan **por camión**, no por documento:

```python
flete_mercado_cam = precio_promedio_empresa / 1.0  # Ya en USD/doc
flete_mercotruck_cam = flete_reciente / 1.0       # Ya en USD/doc
```

---

## Diferencia Porcentual

Métrica de competitividad: compara precio de Mercotruck vs precio de mercado.

### Fórmula

```
Diferencia % = ((Flete Mercotruck - Flete Mercado) / Flete Mercado) × 100
```

### Interpretación

| Rango | Significado | Color |
|-------|-------------|-------|
| < -50% | Mercotruck muy por debajo (oportunidad fuerte) | Verde |
| -50% a 0% | Mercotruck por debajo (ventaja competitiva) | Verde |
| 0% a +25% | Mercotruck por encima (revisar) | Rojo/Naranja |
| > +25% | Mercotruck mucho más caro (descartable) | Rojo |

### Ejemplo

```
Flete Mercado: $1,000 USD
Flete Mercotruck: $900 USD

Diferencia % = ((900 - 1000) / 1000) × 100 = -10%
→ Mercotruck 10% más barato (ventaja)
```

### Casos Especiales

```python
# Si falta precio de Mercotruck
if pd.isna(flete_mercotruck) or flete_mercotruck <= 0:
    diff_pct = None

# Si falta precio de mercado
if pd.isna(flete_mercado) or flete_mercado <= 0:
    diff_pct = None

# Si ambos existen
else:
    diff_pct = ((flete_mercotruck - flete_mercado) / flete_mercado) * 100
```

### Ordenamiento

En v5.3, la columna **Diferencia %** es **independiente y ordenable** por separado.

---

## Geographic Matching

Determina qué tan cercana es la ruta operada por Mercotruck vs la ruta de los documentos del prospecto.

### Radios de Distancia

| Tipo Match | Radio | Significado |
|-----------|-------|-------------|
| `EXACTO` | ≤ 50 km | Mismo origen Y mismo destino (dentro de 50 km) |
| `CERCANO` | ≤ 100 km | Al menos un extremo dentro de 100 km |
| `(sin match)` | > 100 km | Fuera de rango operativo |

### Algoritmo

Para cada prospecto, se evalúa contra CADA ruta que opera Mercotruck:

```python
# Entrada:
#  - origen_prospecto, destino_prospecto (coordenadas lat/lon)
#  - origen_mercotruck, destino_mercotruck (coordenadas lat/lon)

# Distancia Haversine
def haversine(lat1, lon1, lat2, lon2):
    """Calcula distancia en km entre dos puntos"""
    R = 6371  # Radio de la Tierra en km
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat/2)**2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c

# Distancia origen
dist_origen = haversine(lat_orig_prosp, lon_orig_prosp, lat_orig_mtruck, lon_orig_mtruck)

# Distancia destino
dist_destino = haversine(lat_dest_prosp, lon_dest_prosp, lat_dest_mtruck, lon_dest_mtruck)

# Determinar tipo de match
if dist_origen <= 50 and dist_destino <= 50:
    match_tipo = "EXACTO"
elif dist_origen <= 100 or dist_destino <= 100:
    match_tipo = "CERCANO"
else:
    match_tipo = None  # No califica
```

### Matriz de Decisión

| Dist Origen | Dist Destino | Match | Razón |
|-------------|--------------|-------|-------|
| ≤ 50 km | ≤ 50 km | EXACTO | Ambos extremos coinciden |
| ≤ 50 km | 50-100 km | CERCANO | Un extremo exacto, otro cercano |
| 50-100 km | ≤ 50 km | CERCANO | Un extremo cercano, otro exacto |
| 50-100 km | 50-100 km | CERCANO | Ambos cercanos (al menos uno) |
| > 100 km | Cualquiera | (descartado) | Fuera de rango |
| Cualquiera | > 100 km | (descartado) | Fuera de rango |

### Implementación Vectorizada

```python
# Calcular distancias con numpy broadcasting
import numpy as np

# Arrays de coordenadas
orig_prosp = np.array([lat_p, lon_p])
dest_prosp = np.array([lat_p, lon_p])
orig_mtruck = np.array([lat_m, lon_m])
dest_mtruck = np.array([lat_m, lon_m])

# Haversine vectorizado
dist_origen = haversine_vectorized(orig_prosp, orig_mtruck)
dist_destino = haversine_vectorized(dest_prosp, dest_mtruck)

# Match lógico
match_tipo = np.where(
    (dist_origen <= 50) & (dist_destino <= 50), 'EXACTO',
    np.where(
        (dist_origen <= 100) | (dist_destino <= 100), 'CERCANO',
        None
    )
)
```

---

## Score de Oportunidad

Métrica global que prioriza prospectos por viabilidad y competitividad.

### Fórmula

```
Score Oportunidad = Total Camiones × Factor Competitividad
```

Donde:

```
Factor Competitividad = {
    2.0   si Diferencia % <= -10%    (Mercotruck 10%+ más barato)
    1.5   si -10% < Diferencia % <= 0%  (Mercotruck ligeramente más barato)
    1.0   si 0% < Diferencia % < 25%   (Mercotruck más caro pero negociable)
    0.5   si Diferencia % >= 25%      (Muy caro, baja prioridad)
    0.0   si Diferencia % = null       (Sin datos de precio)
}
```

### Ejemplo Completo

```
Empresa: XYZ Logistics
Total Camiones: 12
Flete Mercado: $1,200 USD
Flete Mercotruck: $1,000 USD
Diferencia %: -16.7%

Factor Competitividad = 2.0  (porque -16.7% <= -10%)
Score Oportunidad = 12 × 2.0 = 24

Interpretación: Prospecto muy atractivo (24 camiones con 20% descuento)
```

### Casos Especiales

```python
# Si no hay diferencia %
if diff_pct is None:
    score = 0

# Si hay diferencia % pero no hay camiones
if total_camiones == 0:
    score = 0

# Factor de competitividad
if diff_pct <= -10:
    factor = 2.0
elif diff_pct <= 0:
    factor = 1.5
elif diff_pct < 25:
    factor = 1.0
elif diff_pct >= 25:
    factor = 0.5
else:
    factor = 0.0

score = total_camiones * factor
```

### Ordenamiento Predeterminado

Por defecto, los resultados se ordenan **descendente** por Score de Oportunidad:

```
Score 24 > Score 18 > Score 12 > Score 6 > Score 0
```

---

## Categorización de Mercaderías

Clasifica la carga en 30 categorías agrupadas por tipo de bien.

### Mapeo de Categorías

Cada documento posee un campo **Mercadería** (texto descriptivo de la carga) que se mapea a una categoría estándar:

```python
CATEGORIAS_MAP = {
    # Alimentos y Bebidas
    'ALIMENTOS': ['ALIMENTO', 'COMIDA', 'ALIMENITICIO', 'DRINK', 'BEBIDA'],
    'FRUTAS Y HORTALIZAS': ['FRUTA', 'HORTALIZA', 'VERDURA', 'FRUTICOLA'],
    'CARNES Y PESCADOS': ['CARNE', 'PESCADO', 'MARISCO', 'POLLO', 'EMBUTIDO'],
    'PRODUCTOS LACTEOS': ['LACTEO', 'QUESO', 'LECHE', 'YOGUR'],
    
    # Químicos y Petróleo
    'QUÍMICOS': ['QUIMICO', 'REACTIVO', 'SOLVENTE', 'CATALIZADOR'],
    'HIDROCARBUROS': ['PETROLEO', 'GASOLINA', 'DIESEL', 'COMBUSTIBLE', 'NAFTA'],
    'PLÁSTICOS Y POLÍMEROS': ['PLASTICO', 'POLIMER', 'RESINA', 'POLIESTIR'],
    
    # Metales y Materiales
    'METALES': ['METAL', 'ACERO', 'HIERRO', 'ALUMINIO', 'COBRE'],
    'MADERA Y DERIVADOS': ['MADERA', 'TABLERO', 'PAPEL', 'CARTON'],
    
    # Textiles y Confecciones
    'TEXTILES': ['TEXTIL', 'TELA', 'FIBRA', 'HILO'],
    'PRENDAS DE VESTIR': ['PRENDA', 'ROPA', 'ROPA DE CAMA'],
    
    # Electrónica e Industrial
    'ELECTRÓNICA': ['ELECTRO', 'ELECTRONICO', 'CHIP', 'CIRCUITO'],
    'MAQUINARIA': ['MAQUINA', 'MOTOR', 'BOMBA', 'COMPRESOR'],
    
    # Construcción
    'MATERIALES CONSTRUCCIÓN': ['CEMENT', 'LADRILLO', 'TUBO', 'VIDRIO'],
    
    # Otros
    'OTROS': ['OTRO', 'DIVERSO', 'VARIOS']
}

# Lógica de mapeo
def categorizar(mercaderia_texto):
    if not mercaderia_texto:
        return 'OTROS'
    
    txt = mercaderia_texto.upper()
    
    for categoria, palabras_clave in CATEGORIAS_MAP.items():
        for palabra in palabras_clave:
            if palabra in txt:
                return categoria
    
    return 'OTROS'

# Aplicación
df['categoria_principal'] = df['Mercaderia'].apply(categorizar)
```

### Agregación de Categorías por Empresa

Cada prospecto agrupa TODAS las categorías de sus documentos:

```python
# Ejemplo de empresa con 5 documentos
# Doc 1: FRUTAS Y HORTALIZAS
# Doc 2: FRUTAS Y HORTALIZAS
# Doc 3: ALIMENTOS
# Doc 4: QUÍMICOS
# Doc 5: FRUTAS Y HORTALIZAS

# Resultado agregado:
categorias_empresa = [
    'FRUTAS Y HORTALIZAS',  # 3 docs
    'ALIMENTOS',             # 1 doc
    'QUÍMICOS'               # 1 doc
]

# Se muestra en UI como tags: FRUTAS Y HORTALIZAS | ALIMENTOS | QUÍMICOS
```

---

## Historial de Precios

Cada prospecto con una ruta operada por Mercotruck muestra:

### Datos del Historial

```
{
    "n_viajes": 8,                      # Número total de viajes en esa ruta
    "venta_promedio": 1050.50,          # Promedio histórico USD/camión
    "venta_reciente": 1010.25,          # Promedio últimos 90 días USD/camión
    "detalle_viajes": [
        {
            "fecha": "2024-08-01",
            "venta": 1000,
            "fletero": "Transporte ABC",
            "cliente": "Cliente X",
            "mercaderia": "Alimentos"
        },
        ...
    ]
}
```

### Filtros de Historial

Dentro de `/api/prospecto/:rut`, se devuelve:

1. **Viajes en orden descendente por fecha** (más recientes primero)
2. **Marcación de "reciente"** si la fecha está dentro de 90 días
3. **Tabla interactiva** con paginado (10 viajes por página)

---

## Columnas del Resultado Final

Cada prospecto en el listado tiene estas columnas ordenables:

### Columna: Empresa

**Tipo:** Texto  
**Origen:** SOFTTRADE (IMPO/EXPO)  
**Descripción:** Nombre legal de la empresa importadora/exportadora  
**Ejemplo:** "XYZ LOGISTICS LTDA."

---

### Columna: RUT

**Tipo:** Texto  
**Origen:** SOFTTRADE (IMPO/EXPO)  
**Descripción:** RUT único de la empresa (sin dígito verificador)  
**Ejemplo:** "76123456"

---

### Columna: Fuente

**Tipo:** Badge (IMPO | EXPO)  
**Origen:** Derivado (según archivo de origen)  
**Descripción:** Dirección del flujo comercial  
**Reglas:**
- `IMPO` = Importa a Chile (flujo Argentina → Chile)
- `EXPO` = Exporta desde Chile (flujo Chile → Argentina)

---

### Columna: Match

**Tipo:** Badge (EXACTO | CERCANO)  
**Origen:** Cálculo Geographic Matching  
**Descripción:** Proximidad de la ruta del prospecto vs ruta Mercotruck  
**Reglas:**
- `EXACTO` = Ambos extremos ≤ 50 km
- `CERCANO` = Al menos un extremo ≤ 100 km

---

### Columna: Transportistas

**Tipo:** Lista de texto  
**Origen:** SOFTTRADE (campo "Transportista" u "Operador")  
**Descripción:** Empresas transportistas que actualmente usan (frecuencia descubierta)  
**Ejemplo:** "TRANSPORT A", "TRANSPORT B", "TRANSPORT C"  
**Regla:** Mostrar máximo 4 primeros; indicar si hay más

---

### Columna: Categorías

**Tipo:** Tags (coloreados)  
**Origen:** Mapeo de Mercadería → Categoría  
**Descripción:** Tipos de carga que mueve la empresa  
**Ejemplo:** `FRUTAS Y HORTALIZAS` | `ALIMENTOS` | `QUÍMICOS`

---

### Columna: Ruta

**Tipo:** Texto  
**Origen:** Cálculo Geographic Matching + Historial Mercotruck  
**Descripción:** Ruta donde Mercotruck opera con historial  
**Formato:** `ORIGEN → DESTINO (PASO)`  
**Ejemplo:** "BUENOS AIRES → ADUANAS CHILENAS (Paso fronterizo)"

---

### Columna: Camiones

**Tipo:** Número entero  
**Origen:** Agregación de documentos por empresa  
**Fórmula:** `SUM(CEIL(Peso / 28,500))`  
**Descripción:** Volumen total de camiones necesarios para los documentos  
**Ejemplo:** 12 camiones

---

### Columna: Documentos

**Tipo:** Número entero  
**Origen:** Contar documentos válidos por empresa  
**Descripción:** Total de transacciones (documentos SOFTTRADE) de esa empresa  
**Ejemplo:** 5 documentos

---

### Columna: Flete Mercado

**Tipo:** USD / Camión  
**Origen:** Promedio SOFTTRADE por empresa  
**Fórmula:** `AVERAGE(Flete por documento)`  
**Descripción:** Precio promedio que pagan actualmente en el mercado  
**Ejemplo:** "$1,200 USD/cam"  
**Casos especiales:**
- Si sin documentos válidos → "no disponible"
- Si el campo está vacío → "no disponible"

---

### Columna: Flete Mercotruck

**Tipo:** USD / Camión  
**Origen:** Historial interno + 90 días reciente  
**Fórmula:** `AVERAGE(Viajes últimos 90d) o AVERAGE(todos los viajes)`  
**Descripción:** Precio promedio que ofrece Mercotruck en esa ruta  
**Ejemplo:** "$1,000 USD/cam"  
**Casos especiales:**
- Si sin historial en esa ruta → "a consultar"
- Si hay historial pero no es reciente → usar promedio histórico

---

### Columna: Diferencia %

**Tipo:** Porcentaje con color  
**Origen:** Cálculo comparativo  
**Fórmula:** `((Flete Mercotruck - Flete Mercado) / Flete Mercado) × 100`  
**Descripción:** Ventaja o desventaja competitiva  
**Ejemplo:** "-10%" (Mercotruck 10% más barato)  
**Color:**
- Verde: ≤ 0% (ventaja Mercotruck)
- Naranja/Rojo: > 0% (desventaja Mercotruck)  
**Ordenamiento:** Ordenable de forma independiente (v5.3)

---

### Columna: Score Oportunidad

**Tipo:** Número  
**Origen:** Cálculo multi-factor  
**Fórmula:** `Total Camiones × Factor Competitividad`  
**Descripción:** Prioridad del prospecto basada en volumen y precio  
**Ejemplo:** 24 (oportunidad muy atractiva)  
**Ordenamiento:** Descendente por defecto (primera visualización)

---

### Columna: Último Envío

**Tipo:** Texto con relativos  
**Origen:** Fecha más reciente en SOFTTRADE  
**Descripción:** Proximidad de actividad comercial  
**Formato:**
- Reciente: "12d atrás (2024-08-01)" (< 90 días)
- Histórico: "2024-08-01"  
- Desconocida: "—"

---

## Filtros y Búsqueda

### Búsqueda por Empresa (Texto Libre)

**Campo:** Input de texto  
**Lógica:** CONTIENE (case-insensitive)  
**Ejemplos:**
- "XYZ" → Busca "XYZ LOGISTICS LTDA."
- "logistic" → Busca cualquier nombre con "LOGISTIC"
- "123" → Busca RUT que contiene "123"

**Implementación:**
```javascript
// Frontend (JavaScript)
filtrar_por_empresa(texto) {
    const t = texto.toUpperCase().trim();
    if (!t) return all;  // Si vacío, devuelve todos
    return all.filter(p => 
        p.empresa.includes(t) || p.rut.includes(t)
    );
}
```

---

### Filtro por Fuente (IMPO/EXPO)

**Campo:** Checkbox múltiple  
**Opción 1:** IMPO (Importaciones)  
**Opción 2:** EXPO (Exportaciones)  
**Lógica:** OR (acepta cualquiera)

**Implementación:**
```javascript
filtrar_por_fuente(fuentes_seleccionadas) {
    if (fuentes_seleccionadas.length === 0) return all;
    return all.filter(p => fuentes_seleccionadas.includes(p.fuente));
}
```

---

### Filtro por Match (EXACTO/CERCANO)

**Campo:** Checkbox múltiple  
**Opción 1:** EXACTO  
**Opción 2:** CERCANO  
**Lógica:** OR (acepta cualquiera)

**Implementación:**
```javascript
filtrar_por_match(matches_seleccionados) {
    if (matches_seleccionados.length === 0) return all;
    return all.filter(p => matches_seleccionados.includes(p.match_tipo));
}
```

---

### Filtro por Categoría (Dropdown)

**Campo:** Select dropdown  
**Opciones:** Todas las categorías presentes en los datos  
**Lógica:** CONTIENE (prospecto tiene esa categoría)

**Implementación:**
```javascript
filtrar_por_categoria(categoria_seleccionada) {
    if (!categoria_seleccionada) return all;
    return all.filter(p => 
        p.categorias_list && p.categorias_list.includes(categoria_seleccionada)
    );
}
```

**Población dinámica:**
```javascript
// Endpoint GET /api/categorias
async function cargarCategorias() {
    const data = await fetch('/api/categorias').then(r => r.json());
    const select = document.getElementById('fcat');
    data.categorias.forEach(cat => {
        const opt = document.createElement('option');
        opt.value = cat;
        opt.textContent = cat;
        select.appendChild(opt);
    });
}
```

---

### Combinación de Filtros

Todos los filtros se aplican en **AND lógico:**

```
Resultados = (Búsqueda POR Empresa)
           AND (Fuente IMPO o EXPO)
           AND (Match EXACTO o CERCANO)
           AND (Categoría seleccionada)
```

**Ejemplo:**
- Búsqueda: "XYZ"
- Fuente: IMPO
- Match: EXACTO
- Categoría: ALIMENTOS

→ Devuelve solo empresas con "XYZ" que: importan, tienen ruta EXACTO, y mueven ALIMENTOS

---

## Detalles de Implementación Técnica

### Motor de Lectura Excel

```python
def _engine():
    try:
        import python_calamine
        return 'calamine'  # ~3x más rápido
    except ImportError:
        return 'openpyxl'  # Fallback

# Uso
df = pd.read_excel(file, engine=_engine())
```

### Normalización Vectorizada

```python
# Todas las columnas de texto → mayúsculas + trim
for col in df.columns:
    if df[col].dtype == object:
        df[col] = df[col].str.upper().str.strip()
```

### Distancia Haversine (Vectorizada)

```python
import numpy as np

def haversine_vectorized(lat1, lon1, lat2, lon2):
    """Calcula distancia en km (soporta arrays)"""
    R = 6371
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = (np.sin(dlat/2)**2 + 
         np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon/2)**2)
    c = 2 * np.arcsin(np.sqrt(a))
    return R * c
```

### Formateo de Moneda

```python
# Parseo de valores con formato "$3,050.00"
def parse_currency(value):
    if not value or pd.isna(value):
        return None
    s = str(value).replace('$', '').replace(',', '').strip()
    try:
        return float(s)
    except:
        return None

df['Flete'] = df['Flete'].apply(parse_currency)
```

---

## Advertencias y Limitaciones Conocidas

### EXPO Mendoza (Destino = MENDOZA)

**Problema:** ~25% de documentos EXPO tienen destino "MENDOZA", que es una aduana de cruce, no destino final.

**Solución v5.3:** Disclaimer + filtro opcional (sin implementar automáticamente aún)

**Plan futuro:** Inferencia de destino final basada en patrones o datos adicionales.

---

### Ruta "Camionera Mendocina"

**Problema:** Algunos registros históricos contienen "camionera mendocina" que no corresponden a rutas reales.

**Solución:** Excluir de historial cuando se identifiquen.

---

## Resumen de Validaciones y Cálculos

| Concepto | Tipo | Fuente | Fórmula/Regla |
|----------|------|--------|---------------|
| **Camiones** | Agregación | Documentos | CEIL(Peso / 28,500) |
| **Flete Mercado** | Promedio | SOFTTRADE | AVG(Flete por empresa) |
| **Flete Mercotruck** | Promedio | Historial | AVG(Viajes 90d) o AVG(todos) |
| **Diferencia %** | Comparativo | Cálculo | ((MT - Mercado) / Mercado) × 100 |
| **Match Tipo** | Clasificación | Distancia | EXACTO: ≤50km; CERCANO: ≤100km |
| **Score Oportunidad** | Prioridad | Multifactor | Camiones × Factor Competitividad |
| **Categoría** | Clasificación | Mapeo | Palabra clave en descripción mercadería |

---

**Fin de documentación v5.3**
