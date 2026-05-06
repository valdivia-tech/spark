# [FALLIDO] Flujo de potencia en 2603-BD-OP-COORD-DMAP (Laboral Diurno)
Fecha: 2026-04-06
Tarea: "Activar el caso de estudio 'Laboral Diurno', correr flujo de potencia y extraer resultados o diagnóstico."

## Qué se intentó
- Se intentó activar el caso de estudio 'Laboral Diurno', pero se descubrió que 'Laboral Diurno' es un **Escenario** (`IntScenario`), no un Caso de Estudio. El único caso de estudio es 'Base SEN'.
- Se activó el caso 'Base SEN' y luego el escenario 'Laboral Diurno'. Esto corrigió los problemas de topología (0 barras aisladas), pero el flujo de potencia divergió.
- Se realizó un diagnóstico de divergencia detectando un desbalance masivo: Generación (~4.7 GW) vs Carga (~8.9 GW), con un déficit de ~4.2 GW.

## Por qué falló
- El escenario 'Laboral Diurno' en esta base de datos operativa (BD-OP) viene con un despacho de generación insuficiente para cubrir la carga total del sistema.
- Al haber un desbalance de >4 GW, el nodo de referencia (slack) o la red externa (ElmXnet) no pueden compensar la diferencia sin causar el colapso del flujo de potencia o problemas numéricos.

## Recomendación
- El modelo requiere un redespacho manual o escalamiento de generación antes de correr el flujo, o bien la activación de múltiples generadores que están fuera de servicio en el escenario original para balancear la carga.
- Ver experiencias previas `pf-2603-*` para intentos de corrección (que también han sido difíciles debido a la fragmentación de la red).
