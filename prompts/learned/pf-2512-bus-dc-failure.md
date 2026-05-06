# [FALLIDO] Flujo de potencia DC con Slack Distribuido (2512-bus)
Fecha: 2026-04-06
Tarea: "Flujo de potencia DC con Slack Distribuido en proyecto 2512-bus"

## Qué se intentó
- Se configuró un flujo de potencia DC (`iopt_net=1`) con Slack Distribuido (`iopt_ds=1`).
- Se realizó una activación radical (`outserv=0`) de todos los objetos eléctricos (`Elm*`).
- Se ejecutaron los scripts DPL `ON_OFF` presentes en el proyecto.
- Se despacharon generadores al 70% de su capacidad nominal.

## Por qué falló
- El flujo de potencia divergió incluso en modo DC.
- El diagnóstico reveló **756 barras aisladas** y la ausencia de una Red Externa (`ElmXnet`) activa que sirviera como Slack/Referencia.
- Aunque se usó Slack Distribuido, el sistema lineal $B'\theta = P$ sigue siendo singular si hay islas sin referencia o si el sistema completo no tiene una referencia angular.
- El desbalance de potencia fue de ~2116 MW (Gen: 7445 MW, Load: 9562 MW).

## Recomendación
- El modelo '2512-bus' requiere una reconstrucción topológica manual o un script que identifique y conecte componentes huérfanos. 
- La divergencia en DC es un indicador claro de que el problema no es la no-linealidad (AC), sino la **singularidad de la matriz de admitancia** debido a falta de conectividad o de un nodo de referencia.
