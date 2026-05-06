# Inspección de Generadores y Activación de Escenario en 2603

Fecha: 2026-04-07
Tarea: "In project 2603-BD-OP-COORD-DMAP.pfd: 1. Activate Study Case 'Base SEN'. 2. Find and activate Scenario 'Laboral Diurno'. 3. Disable all ElmDsl models. INSPECTION TASK: Find all active ElmSym and ElmGenstat, collect attributes, group by Standard/Non-Standard prefixes."

## Lecciones aprendidas
- **Ruta del Proyecto**: El proyecto `2603-BD-OP-COORD-DMAP.pfd` se encuentra en una subcarpeta `..\projects\2603\`. Siempre es mejor verificar la estructura de directorios si falla la carga inicial.
- **Acceso a typ_id**: En algunos entornos, acceder a `obj.typ_id` como propiedad puede fallar (`AttributeError: 'DataObject' object has no attribute 'typ_id'`). Es más seguro usar `obj.GetAttribute('typ_id')`.
- **OutputWindow**: El objeto devuelto por `app.GetOutputWindow()` no es serializable a JSON directamente. Se debe convertir a string o procesar sus mensajes individualmente.
- **Prefijos de Categorización**: La categorización basada en prefijos de `loc_name` (`TER`, `HE`, `FV`, `SOL`, `EOL`) es efectiva para identificar tecnologías en bases de datos del CEN.
- **Desactivación de Modelos DSL**: En bases de operación grandes, desactivar modelos DSL (`ElmDsl`) es un paso común para simplificar cálculos estáticos o inspecciones.

## Script
```python
import sys
import os
import time
import json

pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)
pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def main():
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)

    if not app:
        print("API_START_ERROR")
        return

    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
    
    target_name = "2603-BD-OP-COORD-DMAP"
    proj = None
    for p in user.GetContents("*.IntPrj"):
        if target_name in p.loc_name:
            proj = p
            break
            
    if not proj:
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        for p in user.GetContents("*.IntPrj"):
            if target_name in p.loc_name:
                proj = p
                break

    if not proj:
        print("IMPORT_FAILED")
        return

    proj.Activate()
    
    # 2. Activate Study Case 'Base SEN'
    all_cases = proj.GetContents("*.IntCase", 1)
    study_case = next((c for c in all_cases if c.loc_name == 'Base SEN'), None)
    if study_case:
        study_case.Activate()

    # 3. Find Scenario 'Laboral Diurno'
    all_scenarios = proj.GetContents("*.IntScenario", 1)
    scenario = next((s for s in all_scenarios if s.loc_name == 'Laboral Diurno'), None)
    if scenario:
        scenario.Activate()

    # 4. Disable all ElmDsl models
    dsl_models = app.GetCalcRelevantObjects("*.ElmDsl")
    for dsl in dsl_models:
        dsl.outserv = 1

    # 5. Inspection
    generators = []
    prefixes = ("TER", "HE", "FV", "SOL", "EOL")
    non_standard_summary = {}

    all_gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
    
    for g in all_gens:
        if g.outserv == 0:
            loc_name = g.loc_name
            pgini = g.GetAttribute("pgini") if g.HasAttribute("pgini") else 0.0
            path = g.GetFullName()
            
            typ = g.GetAttribute('typ_id') if g.HasAttribute('typ_id') else None
            
            tech = {
                "cCategory": g.GetAttribute("cCategory") if g.HasAttribute("cCategory") else None,
                "fuel": g.GetAttribute("fuel") if g.HasAttribute("fuel") else None,
                "desc": g.GetAttribute("desc") if g.HasAttribute("desc") else None,
                "typ_id_name": typ.loc_name if typ else None
            }
            
            category = "Standard" if loc_name.startswith(prefixes) else "Non-Standard"
            
            generators.append({
                "loc_name": loc_name,
                "pgini": pgini,
                "path": path,
                "technology_info": tech,
                "category": category
            })
            
            if category == "Non-Standard":
                parts = path.split("\\")
                if len(parts) > 1:
                    parent_path = "\\".join(parts[:-1])
                    non_standard_summary[parent_path] = non_standard_summary.get(parent_path, 0) + 1

    # Handle output window messages safely
    try:
        pf_msgs = str(app.GetOutputWindow())
    except:
        pf_msgs = "Could not retrieve output window messages"

    output = {
        "project": proj.loc_name,
        "generators": generators,
        "non_standard_summary_by_path": non_standard_summary,
        "pf_messages": pf_msgs
    }

    with open(os.path.join(results_dir, "generator_inspection.json"), "w") as f:
        json.dump(output, f, indent=2)
    print(f"Results saved. Total generators: {len(generators)}")

if __name__ == "__main__":
    main()
```
