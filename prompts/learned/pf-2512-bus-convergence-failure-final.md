# [FALLIDO] Flujo de potencia 2512-bus con Red Externa como Slack
Fecha: 2026-04-06
Tarea: "Crear un ElmXnet como Slack, escalar generación a 9500 MW y correr flujo AC"

## Qué se intentó
- Se creó un objeto `ElmXnet` (Red Externa) conectado a la barra 'CENTRAL RALCO 220 kV B1'.
- Se configuró como Slack (SL), 1.0 p.u., 0 grados, con límites de reactiva muy amplios.
- Se escalaron todos los demás generadores (`ElmSym`, `ElmGenstat`) para sumar exactamente 9,500 MW.
- Se corrió el flujo de potencia AC con Flat Start (`iopt_init=0`).

## Por qué falló
- El flujo divergió (`error_code = 1`). 
- A pesar de tener un nodo Slack definido y activo, y un balance de carga-generación razonable (~61 MW de diferencia), el sistema no converge.
- Los atributos de error de potencia (`m:Perr`, `m:Qerr`) no se poblaron, lo que sugiere que la divergencia ocurrió en una etapa temprana del proceso iterativo o por problemas topológicos insalvables (islas sin referencia, transformadores con taps fuera de rango, etc.).

## Recomendación
- El modelo '2512-bus' parece tener problemas estructurales de consistencia de datos o topología que impiden la convergencia del flujo AC estándar, incluso proporcionando una referencia infinita.
- Se recomienda una revisión manual exhaustiva en PowerFactory para identificar islas aisladas o errores de modelación de red.
