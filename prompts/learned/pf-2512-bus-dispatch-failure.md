# [FALLIDO] Flujo de potencia 2512-bus con activación masiva de generadores
Fecha: 2026-04-06
Tarea: "Activar todos los generadores, despachar carga+4% y correr flujo AC con Flat Start"

## Qué se intentó
- Se importó el proyecto `2512-bus.pfd`.
- Se activaron todos los generadores (`ElmSym`, `ElmGenstat`) estableciendo `outserv=0`.
- Se calculó la carga total (sumando `plini` de `ElmLod`).
- Se despachó la generación proporcionalmente a la potencia nominal (`sgnom`) para cubrir la carga + 4%.
- Se definió el nodo Slack (primero buscando `ElmXnet`, si no, el `ElmSym` de mayor `sgnom`).
- Se ejecutó el flujo de potencia con `Flat Start` (iopt_pst=1).

## Por qué falló
- El flujo divergió (`error_code = 1`).
- Activar todos los generadores fuera de servicio simultáneamente probablemente creó un estado inicial inestable o inconsistente (conflictos de tensión o islas sin balance).
- El sistema `2512-bus` es estructuralmente propenso a divergencias en AC sin una configuración muy precisa de despacho y topología.

## Recomendación
- No activar todos los generadores indiscriminadamente; usar los escenarios predefinidos del proyecto si existen.
- Verificar la existencia de islas eléctricas aisladas.
- Seguir el protocolo de "MANDATORY STOP" ante divergencias para evitar bucles infinitos de intentos fallidos.
