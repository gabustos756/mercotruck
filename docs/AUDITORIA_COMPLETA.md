Aquí tenés la auditoría completa de appRender.py (

appRender.py
) y la matriz comparativa detallada frente a appSample.py, mercotruck demo.html y la aplicación real del proyecto (app/).

1. Auditoría de appRender.py
¿Es realmente la versión final del MVP?
appRender.py fue la versión adaptada para intentar desplegar la app en Render.com (plataforma Cloud).

Ventajas que introdujo:
Rutas relativas (BASE_DIR / datos).
Variables de entorno para parámetros de negocio (FLETE_MIN, FLETE_MAX, DOCS_MIN, RADIO_KM).
Compatibilidad con servidores WSGI de producción (gunicorn).
Desventajas / Simplificaciones:
Simplificó el matching: Redujo el radio de búsqueda a una sola variable RADIO_KM = 100 (perdiendo el scoring fino de 50km EXACTO vs 100km CERCANO que tenía appSample.py).
Problema de Arquitectura: Procesa archivos Excel pesados (~40 MB) en memoria en cada arranque con pandas. Esto provocó que el plan gratuito de Render colapsara por falta de memoria RAM (motivo por el cual ese despliegue quedó descartado).
2. Matriz Comparativa de Componentes
Dimensión	appRender.py	appSample.py	mercotruck demo.html	App Real (app/)
Tecnología Base	Flask + Pandas (Monolítico)	Flask + Pandas (Monolítico)	HTML + CSS + JS Vanilla (Offline)	FastAPI + SQLAlchemy Async + SQLite/PostgreSQL
Fuente de Datos	Lee .xlsx en memoria en cada arranque.	Lee .xlsx en memoria en cada arranque.	Objeto estático var DATA en JS.	Base de Datos Relacional (prospects, shipments, routes) vía ETL.
Cálculo de Camiones	kg / 28.000 (bultos ligeros) o kg / 28.500.	Fijado a kg / 28.500 constante.	kg / 28.000 o kg / 28.500 visual.	Configurable en backend (truck_capacity_kg = 28500.0).
Matching Geoespacial	Haversine con radio único de 100km.	Radio fino: 50km EXACTO / 100km CERCANO.	Datos precalculados (Score 0 a 7 pts).	MatchingEngine multinivel (Reciente 90d $\rightarrow$ Histórico $\rightarrow$ Tarifario Maestro).
Experiencia de Usuario (UI/UX)	Tabla básica expandible con texto simple.	Modal emergente ("Ficha") + script con botón de copiar.	Máximo nivel visual: Tarjetas KPI, Tooltips interactivos, filtro por país, badges.	Jinja2 + Dashboard interactivo con autocompletado y paginado server-side.
3. Diferencias Claves en la Lógica de Negocio
Lógica de Matching e Historial (90 días):

En appRender.py y appSample.py, el matching se calcula on-the-fly promediando todas las rutas históricas que caen en el radio de 100km.
En la App Real (app/domain/services/matching_engine.py), la lógica es más avanzada y prioriza en 3 niveles:
Prioridad 1: Viajes operados por Mercotruck en los últimos 90 días.
Prioridad 2: Histórico general de viajes.
Prioridad 3: Tarifario Maestro de Referencia (MercotruckTariff).
Cálculo de Tarifas y Comparativa de Precio:

En appRender.py, diff_pct = (tarifa_merc - tarifa_comp) / tarifa_comp * 100. (Si el resultado es positivo, indica que Mercotruck es más caro).
En mercotruck demo.html, la lógica invierte el foco comercial mostrando directamente el ahorro en dólares por mes para el cliente ((flete_mercado - flete_mercotruck) * camiones).
Performance y Escalabilidad:

appRender.py y appSample.py demoran 30 a 60 segundos en arrancar y consumen >500 MB de RAM procesando Excel en cada inicio.
La App Real (app/) procesa los Excel una sola vez mediante un Pipeline de ETL (app/etl/pipeline.py), guardando todo en base de datos. Las consultas del dashboard responden en milisegundos.
4. Propuesta de Fusión (Roadmap Estratégico)
La arquitectura de la App Real (app/) es infinitamente superior a los scripts monolíticos Flask (appRender / appSample). Por lo tanto, la fusión consiste en mantener el backend de app/ e incorporar la riqueza visual y comercial de mercotruck demo.html y appSample.py.

Elementos a Fusionar/Rescatar en la App Real (app/):
Rescatar de mercotruck demo.html (Nivel Visual / Comercial):

Tooltip de Origen de Precio: Al pasar el mouse sobre la tarifa Mercotruck, desplegar el cuadro con la ruta histórica de origen, mercadería matcheada y los 7 puntos de similitud (dots).
Barra de Filtro por País (Pabellón de Banderas): Filtros rápidos (Todos, Chile, Brasil, Uruguay, Paraguay).
Tarjetas KPI Top: Mostrar clientes totales, match exacto, match cercano, camiones potenciales y móntulo total de ahorro mensual USD en juego.
Ficha de Llamada + Script con botón "Copiar": Integrar el botón para copiar al portapapeles el argumento de venta listo para el equipo comercial.
Rescatar de appSample.py (Lógica de Negocio):

Opportunity Score: Ordenar la lista de clientes priorizando Volumen de Camiones × Ventaja de Precio para que los comerciales llamen primero a las cuentas más rentables.
Descartar Definitivamente:

Descartar el motor de lectura directa de Excel al vuelo de appRender.py (causa timeouts y agota la memoria). Todo debe seguir pasando por la base de datos de la app FastAPI.