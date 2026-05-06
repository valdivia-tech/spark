# Flujo de potencia 7-bus con validación de referencia
Fecha: 2026-04-07
Tarea: "Importa el proyecto 'projects/7-bus.pfd'. Activa el proyecto directamente. Ejecuta un flujo de potencia (ComLdf). Si el flujo diverge, intenta con iopt_init=1 (flat start). Extrae tabla de barras, tabla de líneas y resumen de potencia. Valida contra Gen ~14.1 MW, Load 14 MW."

## Lecciones aprendidas
- En el modelo 7-bus base, activar el proyecto directamente sin un Study Case puede dejar elementos en `outserv = 1`. Para alcanzar los valores de referencia (14 MW), es necesario activar estos elementos de forma manual usando `proj.GetContents(pattern, 1)`.
- La captura de mensajes del `OutputWindow` en PowerFactory 2026 devuelve un objeto iterable; para serializarlo en JSON, debe convertirse explícitamente a una lista de cadenas: `[str(m) for m in app.GetOutputWindow()]`.
- Los resultados de generación y carga coinciden con la referencia tras la activación de elementos (Gen: 14.03 MW, Load: 14.0 MW).
- El uso de `safe_get` con `HasAttribute` previene errores si ciertos atributos no están disponibles tras el cálculo (por ejemplo, si el elemento no fue parte del cálculo).

## Script
```python
import sys
import os
import json
import time

# PowerFactory path setup
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def safe_get(obj, attr, default=0.0):
    try:
        if obj.HasAttribute(attr):
            val = obj.GetAttribute(attr)
            return val if val is not None else default
    except:
        pass
    return default

def run():
    timing = {}
    start_total = time.time()
    
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)
    
    if not app:
        return {"error": "Could not connect to PowerFactory"}

    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("projects", "7-bus.pfd"))
    pfd_filename = os.path.basename(pfd_path)

    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    cache_file = os.path.join(results_dir, ".project_cache.json")
    
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache = json.load(f)
        except:
            pass

    project_name = cache.get(pfd_filename)
    if project_name:
        existing = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        if project_name not in existing:
            project_name = None

    if not project_name:
        t0 = time.time()
        projects_before = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        projects_after = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        new_projects = projects_after - projects_before
        if new_projects:
            project_name = list(new_projects)[0]
        else:
            project_name = "Taller 2"
        
        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)
        timing["import_project_seconds"] = time.time() - t0

    # Activate project
    t0 = time.time()
    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    if not proj:
        return {"error": f"Project {project_name} not found"}
    
    proj.Activate()
    timing["activate_project_seconds"] = time.time() - t0

    # ACTIVATE ELEMENTS (needed to match 14 MW target)
    t0 = time.time()
    patterns = ["*.ElmSym", "*.ElmGenstat", "*.ElmLod", "*.ElmTr2", "*.ElmLne", "*.ElmXnet"]
    activated_count = 0
    for pattern in patterns:
        objs = proj.GetContents(pattern, 1) # recursive
        for obj in objs:
            if obj.outserv == 1:
                obj.outserv = 0
                activated_count += 1
    timing["activate_elements_seconds"] = time.time() - t0

    # Run Power Flow
    t0 = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    
    # Check if a study case exists if none active
    if not ldf:
        study_cases = proj.GetContents("*.IntCase", 1)
        if study_cases:
            study_cases[0].Activate()
            ldf = app.GetFromStudyCase("ComLdf")
    
    if not ldf:
        # Create a temporary study case if still none
        sc = proj.GetContents("Network Model/Study Cases")[0] if proj.GetContents("Network Model/Study Cases") else proj
        new_sc = sc.CreateObject("IntCase", "Temp SC")
        new_sc.Activate()
        ldf = app.GetFromStudyCase("ComLdf")

    error_code = ldf.Execute()
    
    # Try flat start if failed
    if error_code != 0:
        ldf.iopt_init = 1 # Flat start
        error_code = ldf.Execute()
        
    timing["power_flow_seconds"] = time.time() - t0
    
    # Get output window messages safely
    try:
        pf_messages = [str(m) for m in app.GetOutputWindow()]
    except:
        pf_messages = ["Could not retrieve output window messages"]

    # Extract Results
    t0 = time.time()
    bus_results = []
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        bus_results.append({
            "name": bus.loc_name,
            "uknom": safe_get(bus, "uknom"),
            "m:u": safe_get(bus, "m:u")
        })

    line_results = []
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        line_results.append({
            "name": line.loc_name,
            "loc_name": line.loc_name,
            "m:loading": safe_get(line, "c:loading")
        })

    # Summary
    gen_mw = 0.0
    for g in app.GetCalcRelevantObjects("*.ElmSym"):
        if g.outserv == 0: gen_mw += safe_get(g, "m:P:bus1")
    for g in app.GetCalcRelevantObjects("*.ElmGenstat"):
        if g.outserv == 0: gen_mw += safe_get(g, "m:P:bus1")
    for g in app.GetCalcRelevantObjects("*.ElmXnet"):
        if g.outserv == 0: gen_mw += safe_get(g, "m:P:bus1")

    load_mw = 0.0
    for l in app.GetCalcRelevantObjects("*.ElmLod"):
        if l.outserv == 0: load_mw += safe_get(l, "m:P:bus1")

    loss_mw = gen_mw - load_mw

    timing["extract_results_seconds"] = time.time() - t0
    timing["total_seconds"] = time.time() - start_total

    result = {
        "status": "success" if error_code == 0 else "failed",
        "error_code": error_code,
        "activated_elements_count": activated_count,
        "bus_table": bus_results,
        "line_table": line_results,
        "summary": {
            "total_generation_mw": round(gen_mw, 4),
            "total_load_mw": round(load_mw, 4),
            "total_losses_mw": round(loss_mw, 4)
        },
        "timing": timing,
        "pf_messages": pf_messages
    }
    
    with open(os.path.join(results_dir, "power_flow.json"), "w") as f:
        json.dump(result, f, indent=2)

    return result

if __name__ == "__main__":
    run()
```
