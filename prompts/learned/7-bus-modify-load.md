# Modificar carga — 7-bus.pfd
Fecha: 2026-05-04
Tarea: "modify_load 7-bus.pfd active_power_mw=50.0"

## Lecciones aprendidas
- **Atributos de carga**: Para `ElmLod`, la potencia activa se define en `plini` (MW) y la reactiva en `qlini` (Mvar).
- **Serialización JSON**: `app.GetOutputWindow()` devuelve un objeto que no es serializable. Si se requiere incluir mensajes, hay que extraerlos como strings o usar una lista vacía para evitar errores de tipo.
- **SPARK_RESULTS_DIR**: Usar siempre `os.environ.get("SPARK_RESULTS_DIR", "results")` para determinar la ubicación de salida, ya que puede incluir subdirectorios dinámicos para aislamiento de tareas.

## Script
```python
import sys, os, json, time

def run():
    t_start = time.time()
    
    # 1. Initialize PowerFactory
    # Default PF path for 2024
    pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
    if pf_path not in sys.path:
        sys.path.insert(0, pf_path)
    
    pf_root = os.path.dirname(os.path.dirname(pf_path))
    os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')
    
    import powerfactory
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)
    
    if not app:
        print("Failed to get PowerFactory application.")
        sys.exit(1)
        
    RESULTS_DIR = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    timing = {}
    
    # 2. Load project using cache
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
    pfd_filename = os.path.basename(pfd_path)
    cache_file = os.path.join(RESULTS_DIR, ".project_cache.json")
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
        imp = user.CreateObject('CompfdImport', 'ImportPfd')
        imp.SetAttribute("e:g_file", pfd_path)
        imp.g_target = user
        imp.Execute()
        imp.Delete()
        projects_after = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        new_projects = list(projects_after - projects_before)
        if new_projects:
            project_name = new_projects[0]
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        else:
            print(f"Import failed: no new project for {pfd_filename}")
            sys.exit(1)

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    
    if not proj:
        print(f"Project {project_name} not found")
        sys.exit(1)
        
    proj.Activate()
    timing["load_project_seconds"] = time.time() - t_start
    t_mod = time.time()
    
    # 3. Find and modify load
    loads = app.GetCalcRelevantObjects("*.ElmLod")
    if not loads:
        loads = proj.GetContents("*.ElmLod", 1)
        
    if not loads:
        print("No loads (ElmLod) found in project.")
        sys.exit(1)
        
    # Take the first load
    target_load = loads[0]
    
    # Store old values
    old_values = {
        "name": target_load.loc_name,
        "active_power_mw": float(target_load.GetAttribute("plini") or 0.0),
        "reactive_power_mvar": float(target_load.GetAttribute("qlini") or 0.0),
        "scaling_factor": float(target_load.GetAttribute("scale0") or 0.0)
    }
    
    # Apply modifications
    target_load.SetAttribute("plini", 50.0)
    
    # Read new values
    new_values = {
        "name": target_load.loc_name,
        "active_power_mw": float(target_load.GetAttribute("plini") or 0.0),
        "reactive_power_mvar": float(target_load.GetAttribute("qlini") or 0.0),
        "scaling_factor": float(target_load.GetAttribute("scale0") or 0.0)
    }
    
    timing["modify_load_seconds"] = time.time() - t_mod
    
    # 4. Save results
    results = {
        "project": project_name,
        "load_modified": target_load.loc_name,
        "previous_values": old_values,
        "new_values": new_values,
        "timing": timing,
        "pf_messages": [] # Skipping output window objects for now
    }
    
    with open(os.path.join(RESULTS_DIR, "modify_load_results.json"), "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run()
```
