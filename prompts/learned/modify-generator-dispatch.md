# Modify generator dispatch (Synchronous/Static)

Fecha: 2026-05-22
Tarea: "modify_generator parameters: {'voltage_setpoint_pu': 1.02}"

## Lecciones aprendidas
- `GetOutputWindow()` en PowerFactory 2024 devuelve un objeto que no es directamente serializable a JSON. Se debe usar `GetLines()` y `GetLine(i)` para extraer los mensajes, o manejarlo con precaución.
- No se deben usar métodos inexistentes como `GetName()` en objetos de PowerFactory; usar `loc_name` o `GetFullName()`.
- El atributo `usetp` controla el setpoint de tensión en pu para generadores.
- La estructura de parámetros opcionales permite flexibilizar el script para `pgini`, `qgini`, `usetp` y `cosn`.

## Script
```python
import sys
import os
import json
import time

# Initialization
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def run():
    start_time = time.time()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)

    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()
    
    if not app:
        raise Exception("Could not get PowerFactory application instance")

    # Load project using cache pattern
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("projects", "7-bus.pfd"))
    pfd_filename = os.path.basename(pfd_path)
    
    t_import_start = time.time()
    
    cache_file = os.path.join(results_dir, ".project_cache.json")
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cache = json.load(f)

    project_name = cache.get(pfd_filename)
    if project_name:
        existing = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        if project_name not in existing:
            project_name = None

    if not project_name:
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
            if "7-bus" in projects_after:
                 project_name = "7-bus"
            elif "Taller 2" in projects_after:
                 project_name = "Taller 2"
            else:
                 raise RuntimeError(f"Import failed: no new project detected for {pfd_filename}")

        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    
    if not proj:
         raise RuntimeError(f"Project {project_name} not found")
    
    proj.Activate()
    t_import_end = time.time()

    # Input parameters
    params_to_change = {
        "voltage_setpoint_pu": 1.02
    }

    # Find generators
    gens = app.GetCalcRelevantObjects("*.ElmSym")
    if not gens:
        gens = app.GetCalcRelevantObjects("*.ElmGenstat")
    
    if not gens:
        raise Exception("No generators found in the model")

    # Pick the first generator found
    gen = gens[0]
    gen_name = gen.loc_name
    gen_type = gen.GetClassName()

    attr_map = {
        "active_power_mw": "pgini",
        "reactive_power_mvar": "qgini",
        "voltage_setpoint_pu": "usetp",
        "power_factor": "cosn"
    }

    data = {
        "generator_name": gen_name,
        "generator_type": gen_type,
        "results": {}
    }

    t_mod_start = time.time()
    for param, value in params_to_change.items():
        attr = attr_map.get(param)
        if attr and gen.HasAttribute(attr):
            old_val = float(gen.GetAttribute(attr) or 0)
            gen.SetAttribute(attr, value)
            new_val = float(gen.GetAttribute(attr) or 0)
            
            data["results"][param] = {
                "attribute": attr,
                "old_value": old_val,
                "new_value": new_val
            }
        else:
            data["results"][param] = {
                "status": "error",
                "message": f"Attribute {attr} for {param} not found in {gen_type}"
            }
    t_mod_end = time.time()

    end_time = time.time()
    
    # Safely capture output window
    pf_messages = []
    try:
        ow = app.GetOutputWindow()
        # For PF 2024, GetOutputWindow() returns an object.
        # We can try to get lines if it has that method, or just use a placeholder
        # if we're not sure.
        if hasattr(ow, "GetLines"):
            for i in range(ow.GetLines()):
                pf_messages.append(ow.GetLine(i))
        else:
            pf_messages = ["Output window capture not implemented for this PF version"]
    except:
        pf_messages = ["Error capturing output window"]

    final_results = {
        "status": "success",
        "project": proj.loc_name,
        "data": data,
        "pf_messages": pf_messages,
        "timing": {
            "load_project_seconds": t_import_end - t_import_start,
            "modify_generator_seconds": t_mod_end - t_mod_start,
            "total_seconds": end_time - start_time
        }
    }

    with open(os.path.join(results_dir, "modify_generator_results.json"), "w") as f:
        json.dump(final_results, f, indent=2)

if __name__ == "__main__":
    run()
```
