# Spark — Experiencias aprendidas

Índice de tareas resueltas. Lee las relevantes antes de escribir un script nuevo.

| Archivo | Descripción |
|---------|-------------|
| `load-flow-bus-voltages.md` | Importar .pfd, correr flujo de potencia, extraer tensiones de barras |
| `load-flow-loading-report.md` | Flujo de potencia y reporte de carga de líneas y transformadores |
| `load-flow-modify-gen.md` | Modificar un generador/red externa y correr flujo |
| `short-circuit-bus.md` | Configurar y ejecutar cortocircuito trifásico en una barra (IEC 60909) |
| `disconnect-element-low-voltage.md` | Desconectar un transformador (TR2) y detectar barras con tensión < 0.95 pu |
| `sc-line-fault-failure.md` | ❌ [FALLIDO] Cortocircuito en línea al 50% (problemas con eventos en ComShc) |
| `sc-line-fault-success.md` | ✅ Cortocircuito en línea al 30% usando eventos y método Complete |
| `7-bus-sc-line-failure.md` | ❌ [FALLIDO] Falla de extracción de corrientes en corto de línea (7-bus) |
| `cen-2603-power-flow.md` | ⭐ Receta completa para flujo de potencia en BD 2603-OP-COORD-DMAP (10 escenarios validados, 15+ fallas documentadas) |
| `cen-2603-n1-contingency.md` | Análisis N-1 en 500kV y220kV del SEN, scripts batch y lecciones |
| `cen-2603-inventory.md` | Extracción de inventory de activos (líneas, trafos por nivel de tensión) |
| `cen-2603-benchmark.md` | Benchmark de rendimiento (25 flujos) en BD 2603 |
| `error-4002-infrastructure.md` | ❌ Error 4002/7000 — falla de infraestructura PowerFactory, no del modelo |
| `7-bus-power-flow.md` | Estrategia completa para 7-bus.pfd (proyecto simple sin Study Case) |
| `7-bus-balanced-pf.md` | Flujo de potencia AC balanceado en 7-bus con ajustes automáticos y limites Q |
| `7-bus-balanced-pf-2024.md` | Flujo de potencia AC balanceado en 7-bus con corrección de tensión m:U para PF 2024 |
| `list-elements-by-type.md` | Listar elementos por tipo con parámetros clave |
| `7-bus-short-circuit-line.md` | Análisis de cortocircuito monofásico en línea al 0% usando IEC 60909 |
| `7-bus-short-circuit-complete.md` | Cortocircuito en línea usando método Complete y falla bifásica a tierra |
| `7-bus-line-parameters.md` | Extracción de parámetros de impedancia (R1, X1, R0, X0, Z1, Z0, K0) de líneas |
| `7-bus-short-circuit-bus.md` | Cortocircuito trifásico en barra (IEC 60909) con corrientes y contribuciones |
| `set-element-status.md` | Modificar estado de servicio (outserv) de un elemento |
| `modify-generator-dispatch.md` | Modificar parámetros de despacho de un generador (pgini, qgini, usetp) |
| `7-bus-modify-load.md` | Modificar parámetros de una carga (plini, qlini, scale0) |
| `7-bus-modify-load-scaling.md` | Modificar el factor de escala (scale0) de una carga |
| `modify-voltage-setpoint.md` | Modificar setpoint de tensión (usetp) de un generador o red externa |
| `7-bus-modify-shunt-failure.md` | ❌ [FALLIDO] Modificar un ElmShnt en 7-bus (el modelo no contiene shunts) |
| `set-transformer-tap.md` | Ajuste de tap en transformador con validación contra el tipo (TypTr2) |
| `modify-transformer-connection.md` | Modificar conexión de devanados (HV/LV) en TypTr2 |
| `list-elements-7bus-failure.md` | ❌ [FALLIDO] Listar elementos en 7-bus.pfd (Error 4002) |
| `cen-2604-extraction-failure.md` | ❌ [FALLIDO] Extracción de generación en BD 2604 (atributos m:P:bus1 no encontrados) |
