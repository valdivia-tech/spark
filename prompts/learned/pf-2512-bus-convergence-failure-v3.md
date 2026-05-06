# [FALLIDO] Flujo de potencia en sistema 2512-bus (Chile SEN) - Intento 3
Fecha: 2026-04-06
Tarea: "Set slack bus, distributed slack, and disconnect isolated buses in 2512-bus project"

## Qué se intentó
- **Identificación de Slack:** Se buscaron `ElmXnet` (ninguno encontrado) y `ElmSym`. Se seleccionó el generador más grande como referencia.
- **Configuración de Flujo:** Se activó la opción de **Distributed Slack** (`iopt_slk = 1`) en el comando `ComLdf` para distribuir el desbalance.
- **Limpieza Topológica:** Se ejecutó un análisis de topología (`ComTopo`) para identificar y desconectar barras aisladas (aquellas sin energización).
- **Cálculo de Flujo:** Se intentó ejecutar el flujo de potencia AC.

## Por qué falló
- **Divergencia Persistente:** El flujo de potencia divergió de inmediato (`error_code = 1`).
- **Desbalance Extremo:** El sistema presenta un desbalance masivo de **~2.1 GW** (Carga: 9.5 GW, Generación: 7.4 GW). 
- **Límites de Generación:** Incluso con slack distribuido, el déficit del 28% en la generación respecto a la carga impide que el algoritmo de Newton-Raphson converja hacia una solución estable.
- **Atributos de Control:** Se detectó que los objetos `ElmSym` en este modelo específico no exponen los atributos de control estándar (`i_c_pctrl`) directamente, lo que sugiere una parametrización compleja mediante scripts de despacho internos del proyecto original.

## Recomendación
- El modelo es matemáticamente insoluble en su estado actual (déficit de 2 GW).
- Se requiere ajustar el despacho (Pgen) manualmente o activar un escenario que contenga un balance real.
- Verificar si existen generadores estáticos (`ElmGenstat`) o compensadores que deban ser activados.
