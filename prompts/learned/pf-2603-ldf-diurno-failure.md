# [FALLIDO] Flujo de Potencia 'Laboral Diurno' en 2603 - Divergencia con Déficit de 289 MW
Fecha: 2026-04-07
Tarea: "Activar 'Base SEN', escenario 'Laboral Diurno', deshabilitar DSL y correr flujo de potencia en proyecto 2603."

## Qué se intentó
- Se activó el Study Case 'Base SEN' y el Scenario 'Laboral Diurno'.
- Se deshabilitaron todos los modelos `ElmDsl` (outserv=1) para evitar errores de DLLs.
- Se configuró `ComLdf` con flat start (`iopt_init=1`) y continuación en errores (`iopt_errlf=1`).
- Se ejecutó el flujo de potencia AC.

## Por qué falló
- El flujo de potencia divergió (error_code=1).
- Se detectó un déficit de generación de **288.84 MW** (Gen: 9747.62 MW, Load: 10036.46 MW).
- A pesar de tener un desbalance relativamente pequeño (~2.8%) y contar con una máquina de Slack, el sistema no alcanzó la convergencia en el modo AC balanceado. 
- La ausencia de mensajes detallados en el Output Window (debido a cambios en la API `GetLineCount` vs `GetContent` en PF 2026) dificultó identificar el punto exacto de la divergencia (ej. barra con mayor desbalance).

## Recomendación
- Validar si el escenario 'Laboral Diurno' tiene una máquina de Slack con suficiente reserva para cubrir el desbalance de 289 MW.
- Intentar un flujo DC para verificar la factibilidad del despacho antes del flujo AC.
- Investigar el uso de `GetContent()` de `OutputWindow` para recuperar logs; en esta ejecución devolvió una lista vacía.
- Revisar si existen islas eléctricas menores no detectadas por la cuenta de barras aisladas.
