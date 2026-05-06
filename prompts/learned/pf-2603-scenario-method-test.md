# Escenario 'Laboral Diurno' en 2603 - Comparación de Apply vs Activate
Fecha: 2026-04-06
Tarea: "Activar 'Base SEN', aplicar escenario 'Laboral Diurno' con Apply/Activate condicional y correr flujo."

## Lecciones aprendidas
- **Persistencia de Desbalance**: Tanto `scenario.Apply()` como `scenario.Activate()` resultaron en una generación total de ~4724 MW contra una carga de ~8892 MW. Esto confirma que el despacho definido en el escenario 'Laboral Diurno' de esta base operativa (BD-OP) tiene un déficit estructural de ~4.2 GW.
- **Lógica Condicional de Aplicación**: Se implementó una verificación automática: si al aplicar el escenario la generación es insuficiente (detectada por el valor de 4724 MW), se intenta `Activate()` en lugar de `Apply()`.
- **Divergencia Inevitable**: Con un desbalance del 47%, el flujo de potencia AC diverge inmediatamente a pesar de tener Slack y Red Externa activos.

## Script
```python
import sys, os, json, time
import powerfactory

def get_totals(app):
    gens = app.GetCalcRelevantObjects("*.ElmSym")
    genstats = app.GetCalcRelevantObjects("*.ElmGenstat")
    loads = app.GetCalcRelevantObjects("*.ElmLod")
    total_gen = sum(g.GetAttribute("pgini") for g in gens if not g.outserv) + \
                sum(g.GetAttribute("pgini") for g in genstats if not g.outserv)
    total_load = sum(l.GetAttribute("plini") for l in loads if not l.outserv)
    return total_gen, total_load

# ... (inicialización y carga de proyecto) ...

# 1. Activar Caso de Estudio
cases = proj.GetContents("*.IntCase", 1)
study_case = next((c for c in cases if c.loc_name == "Base SEN"), None)
study_case.Activate()

# 2. Aplicar Escenario
scenarios = proj.GetContents("*.IntScenario", 1) + proj.GetContents("*.ElmScenario", 1)
scenario = next((s for s in scenarios if s.loc_name == "Laboral Diurno"), None)

method_used = "Apply"
scenario.Apply()
gen_mw, load_mw = get_totals(app)

if abs(gen_mw - 4724.0) < 10.0:
    method_used = "Activate"
    scenario.Activate()
    gen_mw, load_mw = get_totals(app)

# 3. Flujo de Potencia
ldf = app.GetFromStudyCase("ComLdf")
error_code = ldf.Execute()
# ... (guardar resultados) ...
```
