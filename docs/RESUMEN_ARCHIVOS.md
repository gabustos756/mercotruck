# Resumen de archivos — Mercotruck Prospector (deploy Render)

Estos 6 archivos forman un paquete de despliegue pensado para subir la app a **Render** vía GitHub. Van juntos: `app.py` es el motor, y los demás son configuración/documentación para ponerlo en producción.

> ⚠️ Nota de contexto: esta es la ruta de Render que en su momento quedó descartada (el free tier no daba abasto con los Excel grandes) a favor de Colab + ngrok. Si estos son los archivos "viejos", puede que valga la pena confirmar si `app.py` acá sigue siendo la v5.3 vigente o si quedó desactualizado respecto a la que estás corriendo en Colab.

---

## `app.py` — la aplicación (Flask, v5.3 "Render-ready")

Es el corazón del proyecto: ~900 líneas que hacen todo (backend + frontend embebido). Se organiza en bloques:

**1. Configuración**
- Lee rutas de datos desde `datos/` (relativa al proyecto, ya no hardcodeada a `C:\...`) o desde la variable de entorno `DATA_FOLDER`.
- Parámetros de negocio configurables por variable de entorno, con los valores que ya tenés fijados: `FLETE_MIN=500`, `FLETE_MAX=8000`, `DOCS_MIN=5`, `RADIO_KM=100`, `DIAS_RECIENTE=90`.

**2. Motor de lectura de Excel**
- Detecta si `python_calamine` está disponible y lo usa (más rápido); si no, cae a `openpyxl`.

**3. Diccionarios geográficos**
- `ADUANAS`: ~45 aduanas argentinas con código de 3 dígitos → nombre + coordenadas (lat/lon).
- `DESTINOS_CHILE/BRASIL/URUGUAY/PARAGUAY`: ciudades destino con coordenadas, unificadas en `ALL_DESTINOS`.
- Funciones auxiliares: `_norm()` (normaliza texto sin tildes), `_coords_destino()` (matchea nombre de ciudad contra el diccionario), `_haversine()` (distancia entre dos puntos), `_calc_camiones()` (calcula camiones necesarios según KG/bultos, con el techo de 28.500 kg que tenés definido — aunque acá hay una excepción a <50kg/bulto que usa 28.000 kg, vale la pena revisar si esa es la lógica que querés mantener).

**4. Carga de datos (`_load_data`)**
- Lee `HISTORICO_MERCOTRUCK.xlsx`, filtra por rango de flete válido ($500–$8000) y descarta filas sin coordenadas de origen/destino reconocidas.
- Lee `SOFTTRADE_IMPO.xlsx` y `SOFTTRADE_EXPO.xlsx`, detectando columnas automáticamente por nombre (empresa, documento, kg, bultos, destino, fecha, país, transportista, flete).
- Agrupa todo por empresa en un diccionario `clientes`, acumulando documentos, KG totales, camiones, transportistas y fechas.
- Cachea todo en memoria (`_cache`) para no releer los Excel en cada request.
- **Ojo:** en esta versión, tanto IMPO como EXPO usan la misma lógica genérica de columnas (busca "ORIGEN"/"DESTINO" en el histórico, y "DESTINO"/"PUERTO"/"CIUDAD" en Softtrade). No veo implementada acá la distinción que tenés definida de *Puerto de Embarque* vs *Aduana* para IMPO, ni *Aduana (CHL)* vs *Puerto de Desembarque* para EXPO con DUA como identificador. Tampoco veo el filtro de *EMBARQUE CONFIRMADO* ni el fix pendiente de `destino = MENDOZA`. Puede ser una versión más simple/anterior a esas reglas.

**5. Matching geográfico (`_match`)**
- Compara cada cliente Softtrade contra las rutas históricas de Mercotruck usando distancia Haversine.
- Score: +2 si origen está dentro del radio, +2 si destino está dentro del radio (mismo `RADIO_KM=100` para ambos casos). Si score ≥ 4 → **EXACTO**; si score ≥ 2 → **CERCANO**.
- Esto difiere de la regla que tenés anotada (EXACTO = 50km en ambos extremos, CERCANO = 100km en un extremo) — acá usa un solo radio de 100km para las dos categorías.

**6. Endpoints API**
| Ruta | Función |
|---|---|
| `GET /` | Sirve el HTML/JS embebido (`HTML_TEMPLATE`) |
| `GET /api/clientes` | Devuelve el listado de prospectos (filtrable por `?pais=`), aplicando `DOCS_MIN`, matching y cálculo de tarifas |
| `GET /api/categorias` | Devuelve los destinos únicos para el filtro desplegable |
| `GET /api/exportar` | Exporta el listado como CSV descargable (`mercotruck_leads.csv`) |
| `GET /health` | Chequeo de salud: confirma si encontró los 3 Excel |

**7. Frontend embebido**
- Un único `HTML_TEMPLATE` (string de Python) con HTML + CSS + JavaScript vanilla, sin frameworks.
- Usa la paleta de marca que tenés definida: navy `#0D1117`, teal `#1B5E6B`/`#2980A0`, rojo `#C0392B`.
- Tabla con filas expandibles por cliente, que muestra: transportistas actuales, documentos individuales, y un **script de llamada sugerido** generado dinámicamente (compara tarifa Mercotruck vs competencia y arma el argumento de venta).
- Filtros: país, tipo de match (EXACTO/CERCANO), categoría (destino), búsqueda libre por nombre de empresa.
- Botón de exportar a CSV y columnas ordenables (`sortBy`).

**8. Entry point**
- Corre con `python app.py` en local (puerto 5000 o `$PORT`), o vía `gunicorn` en producción (así lo invoca `render.yaml`).

---

## `render.yaml` — configuración de despliegue en Render

Define un único servicio web tipo Python:
- **Build:** `pip install -r requirements.txt`
- **Start:** `gunicorn app:app --bind 0.0.0.0:$PORT --timeout 300 --workers 1` (un solo worker, timeout de 300s pensado para el procesamiento pesado de Excel al arrancar)
- **Variables de entorno:** fija `PYTHON_VERSION=3.11.0` y `DEBUG=false`

Nota: el timeout acá (300s) es más generoso que el que aparece en el README (120s) — son de versiones distintas del mismo archivo.

## `requirements.txt` — dependencias Python

```
flask==3.0.3      → framework web
pandas==2.2.2      → procesamiento de los Excel/DataFrames
openpyxl==3.1.3    → motor de lectura de Excel (fallback si no hay calamine)
gunicorn==22.0.0    → servidor de producción WSGI
numpy==1.26.4      → cálculos vectorizados
```
Falta `python-calamine` en esta lista — como el código lo importa de forma opcional (con `try/except`), si no está instalado simplemente usa `openpyxl`, más lento pero funcional.

## `_gitignore` → (renombrar a `.gitignore`)

Ignora lo típico de un proyecto Python: `__pycache__/`, `.pyc`, entornos virtuales (`venv/`, `.venv/`), `.env`, artefactos de build, y archivos de sistema (`.DS_Store`, `Thumbs.db`).

Incluye, comentadas, las líneas para excluir los `.xlsx`/`.csv` de `datos/` si en algún momento querés que los datos **no** se suban al repo (incluso siendo privado). Hoy están comentadas, así que los Excel sí se suben a GitHub.

## `_python-version` → (renombrar a `.python-version`)

Fija la versión exacta de Python a **3.11.8**. Esto es más específico que el `3.11.0` que pide `render.yaml` — normalmente el `.python-version` termina teniendo prioridad en plataformas que lo leen (como Render), así que en la práctica se usaría 3.11.8.

## `README.md` — guía de despliegue paso a paso

Manual en español, pensado para alguien sin experiencia en Git/GitHub/Render, con 9 pasos:

1. Organizar la carpeta del proyecto localmente (`app.py` + `datos/` con los 3 Excel)
2. Instalar Git
3. Crear cuenta en GitHub
4. Crear repositorio **privado** (para no exponer los datos)
5. Subir el proyecto con los comandos `git init / add / commit / push`
6. Crear cuenta en Render (con GitHub)
7. Crear el Web Service en Render, conectando el repo y configurando build/start command
8. Esperar el deploy (5–10 min)
9. Acceder a la app vía la URL pública de Render

También cubre: cómo actualizar los datos (reemplazar Excel + `git push`, con redeploy automático), las limitaciones del plan gratuito (la app "duerme" a los 15 min de inactividad, ~30s de arranque en frío, opción Starter a ~$7/mes para que esté siempre activa), y cómo usar `/health` para diagnosticar si los Excel se cargaron bien.

---

## En síntesis

Es un paquete completo y autocontenido para llevar la app de local a producción en Render con GitHub como intermediario. Documentado pensando en vos como usuario sin background técnico. La principal duda que dejo marcada es que la lógica de negocio en este `app.py` (matching, columnas IMPO/EXPO) parece más simple que las reglas que ya tenés validadas y fijadas — conviene chequear si es una versión anterior a la v5.3 que estás usando en Colab, o si hay que portar los ajustes finos que le hiciste después.
