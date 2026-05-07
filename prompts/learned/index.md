# Spark — Experiencias aprendidas

Índice de tareas resueltas. Lee las relevantes antes de escribir un script nuevo.

| Archivo | Descripción |
|---------|-------------|
| `cen-2603-power-flow.md` | ⭐ Receta completa para flujo de potencia en BD 2603-OP-COORD-DMAP (10 escenarios validados, 15+ fallas documentadas) |
| `cen-2604-multi-scenario-pf.md` | ⭐ Multi-escenario sobre 2604 abril 2026: API gotchas (`m:P:bus1` vía GetAttribute, Boost.Python.ArgumentError) + zonas geográficas + discrepancias vs PDF CEN |
| `cen-2603-n1-contingency.md` | Análisis N-1 en 500kV y 220kV del SEN, scripts batch y lecciones |
| `cen-2603-inventory.md` | Extracción de inventario de activos (líneas, trafos por nivel de tensión) |
| `cen-2603-benchmark.md` | Benchmark de rendimiento (25 flujos) en BD 2603 |
| `cen-2604-ernc-extraction.md` | Extracción de datos geográficos y activos (trafos, gen por zona) en BD 2604 |
| `error-4002-infrastructure.md` | ❌ Error 4002/7000 — falla de infraestructura PowerFactory, no del modelo |
| `7-bus-power-flow.md` | Flujo de potencia AC en 7-bus.pfd (proyecto simple sin Study Case) |
| `7-bus-line-parameters.md` | Extracción de parámetros de impedancia (R1, X1, R0, X0, Z1, Z0, K0) de líneas |
| `list-elements-by-type.md` | Listar elementos por tipo (bus, gen, load, line, transformer, etc.) con parámetros clave |
| `7-bus-modify-load.md` | Modificar parámetros de una carga (plini, qlini, scale0) |
| `7-bus-modify-shunt-success.md` | Modificación de pasos activos (`ncapa`) y reactivo (`qcapn`) en un `ElmShnt` |
| `modify-generator-dispatch.md` | Modificar despacho de un generador (pgini, qgini, usetp) |
| `modify-voltage-setpoint.md` | Modificar setpoint de tensión (usetp) de un generador o red externa |
| `modify-transformer-connection.md` | Modificar conexión de devanados (HV/LV) en TypTr2 |
| `set-element-status.md` | Modificar estado de servicio (outserv) de un elemento |
| `set-transformer-tap.md` | Ajuste de tap en transformador con validación contra el tipo (TypTr2) |
| `7-bus-short-circuit-bus.md` | Cortocircuito trifásico en barra (IEC 60909) con corrientes y contribuciones |
| `7-bus-short-circuit-line.md` | Cortocircuito en línea (IEC 60909 y método Complete) |
| `disconnect-element-low-voltage.md` | Desconectar un elemento y detectar barras con tensión < 0.95 pu |
