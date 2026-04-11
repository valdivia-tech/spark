# Inventario de Activos — CEN 2603-BD-OP-COORD-DMAP
Fecha: 2026-04-11
Tarea: "Extraer inventario de líneas y transformadores por nivel de tensión"

## Lecciones aprendidas

- La BD operacional contiene gran cantidad de activos de subtransmisión y distribución (66 kV y menor).
- Activos de 500 kV y 220 kV están casi todos en servicio (disponibilidad >99.9%).
- La mayor cantidad de elementos fuera de servicio se encuentra en transformadores de baja tensión (<66 kV), probablemente alimentadores desconectados en el snapshot SCADA.
- El troncal de 500 kV consiste exactamente en **34 líneas**.

## Receta

1. Activar Study Case `Base SEN`.
2. Activar Scenario (ej. `Laboral Vespertino`).
3. Usar `GetCalcRelevantObjects('*.ElmLne')` y `GetCalcRelevantObjects('*.ElmTr2')` para capturar todos los elementos.
4. Acceder a `bus1` (líneas) y `bushv` (trafos) para obtener `uknom` del terminal.
5. Clasificar por nivel de tensión y estado de servicio.

## Valores de referencia (Laboral Vespertino)

- **Líneas 500 kV**: 34 en servicio
- **Líneas 220 kV**: 1,088 en servicio
- **Transformadores 500 kV**: 6 en servicio
- **Transformadores 220 kV**: 275 en servicio
- **Total elementos analizados**: 3,954
