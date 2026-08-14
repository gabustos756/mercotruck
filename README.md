# 🚛 Mercotruck Enterprise — Plataforma de Inteligencia Logística & Agente de Cotización

Plataforma empresarial en **Python (FastAPI + Jinja2 + Async SQLAlchemy 2.0 + PostgreSQL)** diseñada para la toma de decisiones comerciales, comparativa competitiva de fletes aduaneros y cotización inteligente de envíos internacionales.

---

## 📄 1. Análisis e Ingesta de Datos (`docs/*.xlsx`)

La plataforma procesa y unifica el histórico de cotizaciones de Mercotruck y el registro aduanero internacional de la competencia (Softtrade IMPO/EXPO):

### A. `HISTORICO_MERCOTRUCK.xlsx`
* **Contenido**: 4,938 viajes y cotizaciones históricas operadas por Mercotruck.
* **Procesamiento ETL**:
  * Extracción de las columnas `VENTA` (Precio venta USD por camión) y `COMPRA` (Costo fletero USD por camión).
  * Limpieza y resolución de distorsión monetaria (conversión de valores Pesos ARS/totales a USD unitario).
  * **Poblado Automático del Tarifario Maestro**: Generación de **405 tarifas claves propias** en PostgreSQL agrupadas por `(Origen, Destino, Paso Fronterizo, Categoría)`.

### B. `SOFTTRADE_IMPO.xlsx` & `SOFTTRADE_EXPO.xlsx`
* **Contenido**: Registro aduanero oficial con **31,673 envíos de Importación (Arg → Chile)** y **7,574 envíos de Exportación (Chile → Arg)**.
* **Procesamiento ETL**:
  * Consolidación de **1,122 empresas únicas** (prospectos comerciales).
  * Resolución geográfica de depósitos y puertos a partir de códigos aduaneros de guía (ej. `057` -> San Lorenzo).
  * Cálculo de flete medio pagado por cada empresa a la competencia (Andesmar, Uspallata, etc.).

---

## ⚡ 2. Módulos & Funcionalidades del Sistema

### 📊 A. Dashboard de Toma de Decisiones (`/`)
* **Comparativa Competitiva en Vivo**: Muestra por empresa el volumen de camiones, flete pagado a la competencia vs la Tarifa Propia Sugerida por Mercotruck.
* **Badges de Oportunidad**: Destaca en verde `🟢 Mercotruck -X% (Ahorro)` cuando la tarifa propia genera un ahorro directo para el cliente.
* **Filtros por Operación**: Búsqueda por Razón Social, CUIT/RUT, Categoría de Carga (Alimentos, Químicos, Papel, etc.) y tipo de operación (`IMPO` / `EXPO`).

### 🎯 B. Pantalla Dedicada de Escenarios de Cotización (`/escenarios`)
* **Simulador de 3 Escenarios Financieros en Tiempo Real**:
  1. **🟢 Opción Agresiva**: Cierre rápido con descuento del -10% respecto a la competencia.
  2. **⭐ Opción Recomendada**: Equilibrio óptimo con ahorro del -5% al cliente y margen saludable (~20%).
  3. **🔵 Opción Max-Margin**: Precio al nivel de la competencia para momentos de alta demanda.
* **Perilla / Slider de Ajuste de Margen (15% - 40%)**: Recalcula instantáneamente el precio de venta en USD según el margen bruto deseado.
* **Emisión & Registro de Cotizaciones**: Permite enviar y registrar propuestas oficiales en PostgreSQL (`quote_history`).

### 📊 C. Agente de Cotización de Envíos
* **Tarjetas Ejecutivas Superiores**: Ubicadas en la parte superior de las pantallas para máxima visibilidad (sin sidebars).
* **Piso de Negociación Innegociable**: Alerta cuando un descuento infringe la regla corporativa del **15% de margen mínimo**.
* **Script Comercial Cuantitativo**: Genera el argumento de venta exacto en USD para la llamada telefónica con el cliente.

### 📋 D. ABM Tarifario Propio de Servicios (`/tarifas`)
* Gestor CRUD para crear, modificar o eliminar tarifas maestras de Mercotruck.

### 🚀 E. Reporte de Corredores y Rutas Frecuentes (`/rutas-frecuentes`)
* Identificación de los principales corredores internacionales:
  * **Top 1**: Buenos Aires → Los Andes via Paso Los Libertadores (7,929 camiones, $19.3M U$S volumen).
  * **Top Paso Fronterizo**: **Paso Los Libertadores** (46,864 camiones, ~85% del tráfico transandino).

---

## 🛠️ 3. Requisitos Previos

* **Python 3.11+** (compatible también con Python 3.9 / 3.10 / 3.12).
* **PostgreSQL 14+** instalado y ejecutándose localmente.

---

## 🚀 4. Instructivo de Instalación y Ejecución en Local

### Paso 1: Clonar el Repositorio e Ingresar a la Carpeta
```bash
cd /Users/fgabrielbustos/Documents/Apps/mercotruck
```

### Paso 2: Crear y Activar el Entorno Virtual (Virtualenv)
```bash
# Crear entorno virtual .venv (si no existe)
python3 -m venv .venv

# Activar el entorno virtual en macOS / Linux:
source .venv/bin/activate
```

### Paso 3: Instalar Dependencias
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 4: Crear la Base de Datos en PostgreSQL
Asegúrate de tener PostgreSQL corriendo y crea la base de datos `mercotruck`:
```sql
CREATE DATABASE mercotruck;
```

*(Si necesitas ajustar credenciales de PostgreSQL, edita las variables en `app/core/config.py` o mediante archivo `.env`)*:
```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/mercotruck
SYNC_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mercotruck
```

### Paso 5: Ejecutar el Pipeline ETL de Ingesta (Poblar Base de Datos)
Este comando procesará los 3 excels de `/docs` y poblará la base de datos PostgreSQL:
```bash
python -m app.etl.pipeline
```

### Paso 6: Iniciar el Servidor Web en Local
Puedes iniciar la aplicación directamente ejecutando:
```bash
python main.py
```
*O usando Uvicorn con recarga automática:*
```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### Paso 7: Abrir en el Navegador
Abre tu navegador web en:
👉 **`http://127.0.0.1:8000`**

---

## 🧪 5. Ejecución de Pruebas Automatizadas (pytest)

Para correr la suite completa de tests de pricing, matching y copilot:
```bash
source .venv/bin/activate
PYTHONPATH=. pytest
```

---

## 📁 6. Estructura del Proyecto (Clean Architecture)

```
mercotruck/
├── app/
│   ├── core/                  # Configuración (config.py) y Sesiones DB (database.py)
│   ├── domain/
│   │   ├── models/            # Modelos SQLAlchemy 2.0 (Prospect, Shipment, Tariff, QuoteHistory)
│   │   ├── schemas/           # DTOs Pydantic v2
│   │   └── services/          # Lógica de dominio (PricingEngine, MatchingEngine, CopilotEngine)
│   ├── etl/                   # Pipeline de ingesta (pipeline.py, historico_parser.py, softtrade_parser.py)
│   ├── api/v1/                # Endpoints REST API
│   ├── web/controllers/       # Controllers web Jinja2 (dashboard, prospect, escenarios, tarifas)
│   └── templates/             # Plantillas HTML con Jinja2
├── docs/                      # Excels de entrada (HISTORICO_MERCOTRUCK, SOFTTRADE_IMPO/EXPO)
├── tests/                     # Suite de pruebas automatizadas (pytest)
├── main.py                    # Punto de entrada de la aplicación
└── requirements.txt           # Dependencias del proyecto
```