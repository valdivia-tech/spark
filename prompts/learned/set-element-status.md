# Modificar estado de servicio de un elemento
Fecha: 2026-05-04
Tarea: "set_element_status: sets an element to in-service or out-of-service. Verify the change by reading back outserv. Return previous and new status."

## Lecciones aprendidas
- Para cambiar el estado de servicio se utiliza el atributo `outserv` (0 = en servicio, 1 = fuera de servicio).
- La modificación de `outserv` se aplica directamente al objeto.
- El objeto `OutputWindow` de PowerFactory no es serializable directamente a JSON; se debe convertir a string o manejar el error para evitar fallas en la escritura del archivo de resultados.
- Es fundamental verificar la ruta del proyecto (.pfd) relativa al espacio de trabajo.

## Script
```python
import sys
import os
import time
import json

# Setup PowerFactory path BEFORE importing powerfactory
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def run():
    t_start = time.time()
    timing = {}
    
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)
    
    if not app:
        print("Could not get PowerFactory application")
        return

    # 2. Load Project
    t_load_start = time.time()
    user = app.GetCurrentUser()
    # Path is relative to the workspace
    pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
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
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        else:
            print(f"Import failed for {pfd_path}")
            return

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    
    if proj:
        proj.Activate()
    else:
        print("Project not found")
        return
    
    timing["load_project_seconds"] = time.time() - t_load_start

    # 3. Target Element Logic
    t_action_start = time.time()
    
    lines = app.GetCalcRelevantObjects("*.ElmLne")
    if not lines:
        print("No lines found in the project")
        return
    
    target_line = lines[0] 
    line_name = target_line.loc_name
    
    # Read previous status
    prev_outserv = int(target_line.GetAttribute("outserv"))
    
    # Target status: activate=false -> outserv=1
    new_outserv = 1
    
    # Apply change
    target_line.outserv = new_outserv
    
    # Read back new status
    final_outserv = int(target_line.GetAttribute("outserv"))
    
    timing["modify_element_seconds"] = time.time() - t_action_start
    
    # 4. Result Formatting
    try:
        pf_messages = str(app.GetOutputWindow())
    except:
        pf_messages = "Could not capture output window"
    
    results = {
        "project": project_name,
        "element": {
            "name": line_name,
            "type": "ElmLne",
            "previous_outserv": prev_outserv,
            "new_outserv": final_outserv,
            "success": final_outserv == new_outserv
        },
        "timing": timing,
        "pf_messages": pf_messages
    }
    
    results["timing"]["total_seconds"] = time.time() - t_start
    
    # Save to JSON
    output_path = os.path.join(results_dir, "set_element_status.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    run()
```
