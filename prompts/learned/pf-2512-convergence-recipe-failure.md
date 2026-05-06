# [FALLIDO] Intento de convergencia con receta de despacho y slack en 2512-bus
Fecha: 2026-04-06
Tarea: "Divergence persists due to missing slack bus. Execute specific fix: Case, Scenario, Variations, DPLs, Generation Scaling, Slack Assignment (Xnet or Jahuel/Quillota/etc.), Topology, ComLdf."

## Qué se intentó
1.  Se activó el proyecto `2512-bus.pfd`, el caso `Base SEN 2030 Día`, el escenario `ERV Maxima_Final_Dia_2030_ETF` y las variaciones `Flujo 2030`, `Flujo_2030`, `Plan de Obras`.
2.  Se ejecutaron más de 100 scripts DPL con 'ON_OFF' en su nombre.
3.  Se activaron todos los generadores y se escaló la generación (`pgini`) para intentar alcanzar `Pload + 500 MW` (~10,061 MW).
4.  Se asignó un bus Slack: se encontró y activó un `ElmXnet` (`REF_SLACK`) configurado como `SL`.
5.  Se ejecutó el flujo de potencia AC (Newton-Raphson, Flat Start).
6.  Se reintentó sin límites de potencia reactiva (`iopt_lim=0`).

## Por qué falló
- A pesar del escalamiento de despacho planeado y la asignación de un nodo Slack explícito, el flujo de potencia divergió (`error_code: 1`).
- El diagnóstico posterior mostró que la generación activa en el modelo permaneció en ~7445 MW frente a una carga de ~9561 MW (desbalance de ~2.1 GW), lo que sugiere que las modificaciones de `pgini` en la memoria del objeto no se reflejaron o no fueron suficientes ante la complejidad del sistema 2030.
- La desconexión de buses aislados no pudo realizarse de forma efectiva sin una convergencia previa para identificar tensiones nulas, y el comando `ComNet` no se comportó como un comando ejecutable estándar en este entorno.

## Recomendación
- El sistema 2030 requiere una validación manual profunda de la conectividad entre las zonas de generación y los centros de carga.
- La gran cantidad de scripts `ON_OFF` y variaciones sugiere una topología altamente dinámica que puede estar dejando islas incompletas o sin referencia a pesar de la activación masiva de elementos.
- Se recomienda diagnosticar por zonas (Norte, Centro, Sur) para localizar el punto de falla en las iteraciones.
