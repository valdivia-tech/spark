# [FALLIDO] Intento de corregir convergencia escalando despacho en sistema 2512-bus
Fecha: 2026-04-06
Tarea: "Ajustar despacho de generadores, relajar límites de slack y correr flujo AC con Slack Distribuido"

## Qué se intentó
- **Escalamiento de despacho:** Se multiplicó el `pgini` de todos los generadores síncronos activos por un factor de ~1.3227 para alcanzar un objetivo de 9,848 MW.
- **Configuración de Slack:** Se seleccionó el generador con mayor despacho como referencia, relajando sus límites de potencia reactiva (`qmin`, `qmax`) a ±99,999 Mvar.
- **Slack Distribuido:** Se configuró el comando `ComLdf` con `iopt_slk = 1` (Slack Distribuido) y `iopt_std_slk = 2` (según Potencia Nominal/Pmax).
- **Ejecución:** Se corrió el flujo de potencia AC en el caso de estudio "Base SEN 2030 Día".

## Por qué falló
- **Divergencia Persistente:** A pesar de haber equilibrado la potencia activa (Generación: 9,848 MW vs Carga: 9,561 MW), el flujo de potencia divergió inmediatamente (`error_code = 1`).
- **Desbalance de Reactiva/Voltaje:** El sistema SEN de Chile es extremadamente sensible a la distribución de potencia reactiva y perfiles de tensión. Un escalamiento lineal de P sin ajustar Q o los setpoints de tensión (`usetp`) probablemente provocó problemas de convergencia local en áreas alejadas del slack.
- **Complejidad Topológica:** Con 31,000 barras, errores menores en transformadores o líneas pueden causar divergencia si no se realiza un control coordinado de voltajes.

## Recomendación
- No realizar escalamientos lineales globales en este sistema. 
- Se requiere un despacho de potencia reactiva coordinado o la activación de compensadores estáticos que no fueron incluidos en este ajuste.
- El modelo parece requerir una topología limpia (aislar islas sin generación/carga) antes del cálculo.

## Script
```python
import sys
import os
import json
import time
import powerfactory

def run():
    app = powerfactory.GetApplication()
    user = app.GetCurrentUser()
    project_name = "2512-BD-LP-COORD-DPL_V1"
    proj = next((p for p in user.GetContents("*.IntPrj") if project_name in p.loc_name), None)
    proj.Activate()

    case_name = "Base SEN 2030 Día"
    study_case = next((c for c in proj.GetContents("*.IntCase", 1) if case_name in c.loc_name), None)
    study_case.Activate()

    active_gens = [g for g in app.GetCalcRelevantObjects("*.ElmSym") if g.outserv == 0]
    target_gen_mw = 9848.0
    current_gen_mw = sum(g.GetAttribute("pgini") for g in active_gens)
    scaling_factor = target_gen_mw / current_gen_mw

    for g in active_gens:
        p_old = g.GetAttribute("pgini")
        g.SetAttribute("pgini", p_old * scaling_factor)

    slack_gen = max(active_gens, key=lambda g: g.GetAttribute("pgini"))
    for attr in ["qmin", "c:qmin", "qmin_tot"]:
        if slack_gen.HasAttribute(attr): slack_gen.SetAttribute(attr, -99999.0)
    for attr in ["qmax", "c:qmax", "qmax_tot"]:
        if slack_gen.HasAttribute(attr): slack_gen.SetAttribute(attr, 99999.0)
    
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_slk = 1       # Distributed slack
    ldf.iopt_std_slk = 2   # Based on Pmax
    error_code = ldf.Execute()
    
    # Report logic...
```
