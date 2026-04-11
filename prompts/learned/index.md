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
| `cen-2603-power-flow.md` | ⭐ Receta completa para flujo de potencia en BD 2603-OP-COORD-DMAP (10 escenarios validados, 15+ fallas documentadas) |
| `cen-2603-n1-contingency.md` | Análisis N-1 en 500kV y 220kV del SEN, scripts batch y lecciones |
| `cen-2603-inventory.md` | Extracción de inventario de activos (líneas, trafos por nivel de tensión) |
| `error-4002-infrastructure.md` | ❌ Error 4002/7000 — falla de infraestructura PowerFactory, no del modelo |
| `7-bus-power-flow.md` | Estrategia completa para 7-bus.pfd (proyecto simple sin Study Case) |
