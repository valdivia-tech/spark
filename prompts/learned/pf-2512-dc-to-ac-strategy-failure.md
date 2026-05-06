# [FALLIDO] DC-to-AC Convergence Strategy (2512-bus)
Fecha: 2026-04-06
Tarea: "DC-to-AC convergence strategy for project 'projects/2512-bus.pfd' including case activation, ON_OFF scripts, iterative generator scaling, and slack placement at specific substations."

## Qué se intentó
- Configuración de caso 'Base SEN 2030 Día', escenario 'ERV Maxima_Final_Dia_2030_ETF' y variaciones 'Flujo 2030', 'Flujo_2030', 'Plan de Obras'.
- Ejecución de scripts DPL que inician con 'ON_OFF'.
- Escalamiento iterativo de generadores (factor 1.1) hasta superar 10,500 MW y balancear carga + 500 MW.
- Asignación manual de slack (`ip_ctrl=0`) en generadores de Alto Jahuel, Polpaico o Quillota.
- Intento de Flujo de Potencia Lineal (DC, `iopt_net=1`).
- Intento de Flujo AC (`iopt_net=0`) usando los resultados de DC como punto de partida (`itask=1`).

## Por qué falló
- El flujo de potencia lineal (DC) no convergió (`error_code != 0`).
- Si un flujo DC no converge, generalmente indica problemas topológicos críticos: islas eléctricas sin barras de referencia (slacks) o falta total de conectividad en el área de interés. 
- En el proyecto 2512-bus, las variaciones 'Plan de Obras' suelen introducir nueva infraestructura que, si no está correctamente activada o conectada, genera islas aisladas.

## Recomendación
- Revisar la topología del escenario 2030 en PowerFactory manualmente.
- Verificar si el generador designado como Slack (o la Red Externa) está físicamente conectado a la red principal en el modelo de variaciones.
- Los scripts 'ON_OFF' pueden estar dejando partes del sistema desconectadas si no se ejecutan en el orden correcto o si faltan variaciones habilitantes.

## Script (Estructura de la estrategia)
```python
# Setup
case.Activate()
scenario.Activate()
for v in variations: v.Activate()

# DPLs
for dpl in proj.GetContents("*.ComDpl", 1):
    if dpl.loc_name.startswith("ON_OFF"): dpl.Execute()

# Power Balance
while total_pgen < 10500:
    for g in gens: g.pgini *= 1.1

# Slack
target_gen.ip_ctrl = 0 # As requested

# Stage 1: DC
ldf.iopt_net = 1
err_dc = ldf.Execute()

# Stage 2: AC (only if DC ok)
if err_dc == 0:
    ldf.iopt_net = 0
    ldf.itask = 1
    err_ac = ldf.Execute()
```
