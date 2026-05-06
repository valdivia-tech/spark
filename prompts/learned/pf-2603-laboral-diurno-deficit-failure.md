# [FALLIDO] Despacho Laboral Diurno en 2603 - Persistencia de Déficit
Fecha: 2026-04-06
Tarea: "Activar Base SEN, aplicar escenario Laboral Diurno y alcanzar ~9388 MW de generación."

## Qué se intentó
- Activación de `Base SEN`.
- Búsqueda y aplicación de `Laboral Diurno` usando `scenario.Apply()`.
- Búsqueda exhaustiva de variaciones (`IntScheme`) para habilitar generación adicional.
- Aplicación en cascada de otros escenarios (`Laboral Madrugada`, `Vespertino`, etc.) al no alcanzar los 9000 MW.

## Por qué falló
- Los escenarios `IntScenario` en esta base operativa tienen `items_count: 0`, lo que significa que no contienen modificaciones de despacho grabadas.
- La generación se mantiene clavada en **4724.4 MW**, resultando en un déficit de ~4.2 GW respecto a la carga.
- No se encontraron variaciones (`SchmVs`) en el proyecto que permitieran habilitar etapas de expansión o generadores fuera de servicio.
- Sin el despacho de ~9.3 GW, el flujo de potencia diverge inevitablemente por falta de potencia activa.

## Recomendación
- Verificar si el despacho está contenido en un `IntScenario` de otra carpeta o si requiere la ejecución de un script DPL previo para inicializar el despacho desde una fuente externa (SCADA/CSV).
- Confirmar si la base requiere `scenario.Activate()` en lugar de `Apply()`, aunque pruebas previas indican resultados idénticos.
