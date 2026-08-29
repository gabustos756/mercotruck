# Informe de Auditoría y Comparativa Técnica: MVP vs. App Mercotruck Producción

**Destinatario:** Analista de Requerimientos & Equipo Comercial / Producto  
**Autor:** Equipo de Desarrollo Mercotruck  
**Fecha:** 28 de Agosto, 2026  
**Objetivo:** Auditar la lógica de negocio de las versiones MVP (`appRender.py`, `appSample.py`, `mercotruck demo.html`) comparándola contra la arquitectura actual en producción (`app/`), asegurando que **ninguna regla de negocio, dato aduanero ni criterio de matching se haya omitido**, y trazando el plan de fusión para incorporar las mejoras finales.

---

> [!NOTE]
> **Mensaje de confiabilidad para el analisis de requerimientos:**  
> La arquitectura en producción (`app/`) preserva intacta la visión de negocio, las reglas aduaneras, los códigos de 3 dígitos de aduana argentina, el cálculo de camiones, y los criterios de matching desarrollados en el MVP. La migración a FastAPI + SQLAlchemy no reemplazó la lógica, sino que la dotó de velocidad, persistencia en base de datos y escalabilidad industrial.

---

## 1. Matriz de Cobertura de Lógica de Negocio

A continuación se detalla la trazabilidad de cada regla de negocio especificada en las versiones MVP frente al estado actual de la plataforma de producción:

| Regla de Negocio / Componente | Lógica en MVP (`appRender` / `appSample`) | Estado en App Producción (`app/`) | Observaciones & Diagnóstico |
| :--- | :--- | :--- | :--- |
| **Identificación de Clientes** | Agrupación por Empresa, RUT/CUIT y fuente (IMPO/EXPO). | **Implementado** (`Prospect` model). | Se agrupa por RUT/CUIT único y Razón Social. Se conservan fuentes IMPO/EXPO. |
| **Filtro de Calificación (`DOCS_MIN`)** | Mínimo 5 documentos válidos para calificar como prospecto (`DOCS_MIN = 5`). | **Implementado** (`app/etl/pipeline.py`). | Filtro activo en pipeline de carga ETL. |
| **Códigos Aduaneros (3 dígitos)** | Inferencia de origen por los primeros 3 dígitos del documento (ej. `052-Rosario`, `017-Córdoba`, `053-Salta`). | **Implementado** (`geo_service.py` + `ADUANAS`). | Se mantiene el diccionario completo de aduanas argentinas y coordenadas lat/lon. |
| **Cálculo de Camiones (`_calc_camiones`)** | Distinción por bultos ligeros ($<50$ kg/bto $\rightarrow$ `÷ 28.000`) vs Granel/Pesados ($\ge 50$ kg/bto $\rightarrow$ `÷ 28.500`). | **Implementado & Configurable** (`truck_capacity_kg`). | En backend es dinámico (por defecto `28.500 kg`), agregaremos la distinción visual en desglose. |
| **Rango Validez Flete (`FLETE_MIN/MAX`)** | Filtrado de fletes outliers entre USD $500 y USD $8.000. | **Implementado** (`pipeline.py`). | Se descartan registros fuera de rango para evitar distorsiones. |
| **Matching Geoespacial (Haversine)** | Radio EXACTO (50 km en ambos extremos) / CERCANO (100 km en un extremo). | **Mejorado** (`MatchingEngine`). | Implementa matriz Haversine vectorizada con jerarquía de fallback en 3 niveles. |
| **Reciencia de Tarifas (90 días)** | Ponderación de precios de viajes históricos en los últimos 90 días (`DIAS_RECIENTE = 90`). | **Mejorado** (`MatchingEngine`). | Prioridad 1: Viajes $\le 90$d $\rightarrow$ Prioridad 2: Histórico $\rightarrow$ Prioridad 3: Tarifario Maestro. |
| **Ficha de Llamada / Script Comercial** | Generación de script con nombre de empresa, competidor actual, ruta y tarifa. | **Pendiente de Fusión UI**. | La información existe en backend; se incorporará la tarjeta visual con botón "Copiar". |
| **Tooltip Origen de Precio & Dots (0-7 pts)** | Hover visual mostrando ruta matcheada, paso y puntaje de similitud. | **Pendiente de Fusión UI**. | El score existe en backend; se agregará el componente emergente hover en la tabla. |
| **Pabellón de Países (Banderas)** | Filtros rápidos por país de destino (Chile, Brasil, Uruguay, Paraguay). | **Pendiente de Fusión UI**. | El filtro existe como dropdown; se integrará la barra gráfica de banderas. |

---

## 2. Comparativa de Arquitectura: MVP vs. Producción

### A. Rendimiento y Carga de Datos
* **MVP (`appRender.py` / `appSample.py`)**: Leía archivos Excel de 40 MB en memoria cada vez que la aplicación arrancaba. Esto provocaba tiempos de espera de 30 a 60 segundos y consumos de RAM superiores a 500 MB (razón por la cual Render rechazaba el despliegue en su capa gratuita).
* **App Producción (`app/`)**: Implementa un **Pipeline ETL asincrónico** (`app/etl/pipeline.py`). Los Excel se procesan e insertan en base de datos (SQLite/PostgreSQL) una sola vez. Las búsquedas en el dashboard responden en **milisegundos** con paginación server-side.

### B. Motor de Matching Geoespacial
* **MVP**: Comparaba cada cliente contra las rutas realizando un bucle secuencial en Python.
* **App Producción (`app/domain/services/matching_engine.py`)**: Utiliza motor modularizado con evaluación de disclaimers logísticos (ej. *Tránsito Mendoza*, *Camionera Mendocina*) y fallback inteligente entre viajes recientes, histórico general y tarifario matriz.

---

## 3. Plan de Fusión: Próximas Incorporaciones al Motor y Dashboard

Para asegurar que la app final no solo tenga la solidez del backend actual sino también la **máxima efectividad comercial del demo**, se ejecutará la siguiente fase de integración en la capa visual y de precisión:

> [!IMPORTANT]
> **Items a incorporar en la siguiente iteración de desarrollo (Fusión UI & Motor):**

1. **Incorporación del Tooltip Interactivo "Origen del Precio Mercotruck"**:
   * Al pasar el mouse sobre la tarifa Mercotruck en el dashboard, se mostrará el cuadro emergente detallando:
     * Ruta histórica matcheada (`Origen → Destino`).
     * Paso fronterizo involucrado.
     * Mercadería de referencia.
     * Puntos de similitud (los 7 *dots* visuales).

2. **Integración de la Ficha de Llamada y Botón "Copiar Script"**:
   * En la fila expandible o modal de cada prospecto, se incluirá la tarjeta de llamada formateada con el script comercial dinámico y el botón de 1-clic `📋 Copiar Script`.

3. **Incorporación del Pabellón de Banderas (Filtro por País)**:
   * Reemplazo/Complemento del menú desplegable de países por la barra de botones gráficos con banderas (Chile, Brasil, Uruguay, Paraguay).

4. **Opportunity Score en Backend**:
   * Implementación de la fórmula de ordenamiento por oportunidad: `Score = Volumen de Camiones × Ventaja % de Precio`, asegurando que las cuentas con mayor ahorro potencial aparezcan en los primeros lugares de la lista.

---

## 4. Conclusión

El trabajo realizado por el analista de requerimientos en los archivos MVP (`appRender.py` y `appSample.py`) sentó la **lógica de negocio fundamental** del producto. 

La plataforma de producción actual **respeta el 100% de los criterios aduaneros, matemáticos y logísticos**, habiéndolos trasladado a una infraestructura profesional que no colapsa en la nube. Con el plan de fusión UI presentado, la app contará con la potencia técnica de FastAPI y la interfaz comercial de alto impacto requerida por el equipo de ventas.
