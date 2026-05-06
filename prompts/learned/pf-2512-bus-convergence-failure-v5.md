# [FALLIDO] Flujo de potencia en sistema 2512-bus con RALCO como despacho manual
Fecha: 2026-04-06
Tarea: "Configurar HE RALCO U1, escalar el resto a 9300 MW y correr flujo AC con slack en una barra"

## Qué se intentó
- Se activó el generador 'HE RALCO U1' (o coincidencia parcial con 'RALCO').
- Se configuró el despacho de RALCO a 500 MW y se puso en servicio su terminal conectada.
- Se escalaron todos los demás generadores (ElmSym, ElmGenstat) para que la suma de sus `pgini` fuera exactamente 9,300 MW.
- Se configuró `ComLdf` con `iopt_slk=0` (Slack en una barra), `itmax=100` y `iopt_init=0` (Flat start).
- Se ejecutó el flujo de potencia AC.

## Por qué falló
- **Ausencia de Barra Slack:** El flujo divergió (`error_code = 1`). La diagnosis indica que no se encontró ninguna barra slack (`slack_bus_found: false`). 
- Al usar `iopt_slk=0`, PowerFactory requiere que al menos un elemento (habitualmente un `ElmXnet` o un `ElmSym` con `i_ref=1`) esté definido como referencia. El ajuste de `i_c_pctrl=2` solicitado no activa automáticamente la propiedad de máquina de referencia en este modelo.
- Existe un desbalance de ~238 MW entre la generación despachada (9,800 MW) y la carga (9,561 MW), el cual no puede ser absorbido por falta de un nodo slack.

## Recomendación
- El modelo requiere la definición explícita de un nodo Slack. Se recomienda activar un `ElmXnet` o marcar un generador mayor como referencia (`i_ref=1`) antes de ejecutar el flujo con `iopt_slk=0`.
- Alternativamente, usar Slack Distribuido (`iopt_slk=1`) si se desea que el desbalance se reparta entre los generadores despachados.
