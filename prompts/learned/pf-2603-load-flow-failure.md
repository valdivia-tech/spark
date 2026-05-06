# [FALLIDO] Flujo de potencia en 2603-BD-OP-COORD-DMAP (Falta Slack y Desconexión Masiva)
Fecha: 2026-04-06
Tarea: "Activar escenario 'Laboral Diurno', identificar generadores, definir slack si falta, y correr flujo de potencia en proyecto 2603."

## Qué se intentó
- Se identificó que 'Laboral Diurno' es un **Escenario de Operación** (`IntScenario`), no un Caso de Estudio (`IntCase`). El caso base es 'Base SEN'.
- Se activó el caso 'Base SEN' y el escenario 'Laboral Diurno'.
- Se detectaron 324 generadores activos pero **ninguna máquina de referencia (Slack)** definida (ni en `ElmXnet`, `ElmSym` ni `ElmGenstat`).
- Se intentó asignar el generador más grande ('TER ANGAMOS U1') como slack usando `SetAttribute("ip_ctrl", 2)`.
- **Error crítico**: `AttributeError: setting attribute 'ip_ctrl' of 'DataObject' object failed`. Esto indica que el atributo no puede ser modificado directamente, posiblemente por estar bloqueado por el escenario o ser un objeto de solo lectura en la API en ese estado.
- Se ejecutó el flujo de potencia sin slack para verificar el estado: divergió inmediatamente (`error_code=1`).
- Los resultados mostraron **0 MW de generación y carga**, con más de 20,000 nodos aislados, sugiriendo que la red está completamente desconectada en ese escenario o que la activación del escenario no habilitó los elementos necesarios.

## Por qué falló
- **Restricción de Atributos**: La API de PowerFactory rechazó la modificación de `ip_ctrl`. Esto suele ocurrir cuando el objeto está siendo controlado por un escenario activo que no permite modificaciones locales o si el usuario no tiene permisos de escritura en la base de datos del proyecto importado.
- **Inconsistencia de Datos**: El escenario 'Laboral Diurno' no parece tener una topología funcional (0 MW detectados), lo que hace imposible la convergencia.

## Recomendación
- No intentar forzar el Slack mediante `ip_ctrl` si el error persiste; es preferible buscar un `ElmXnet` (Red Externa) y activarlo como slack (`i_P_mode=0`), aunque esto también puede fallar si el objeto está bloqueado.
- Verificar manualmente en PowerFactory si el escenario 'Laboral Diurno' realmente contiene datos de despacho válidos.
- El proyecto parece requerir una secuencia de activación de Variaciones (`IntScheme`) además del escenario, la cual no fue especificada.
