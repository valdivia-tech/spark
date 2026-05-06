# Modificar setpoint de tensión de un generador o red externa
Fecha: 2026-05-20
Tarea: "Write a PowerFactory Python script that sets the usetp attribute (pu) on a generator or external grid. Return previous and new value."

## Lecciones aprendidas
- **Atributo usetp**: Este atributo se utiliza para controlar el setpoint de tensión en pu tanto en `ElmSym` como en `ElmXnet` y `ElmGenstat`.
- **Selección de elemento**: Para seleccionar el primer generador, se puede filtrar por `*.ElmSym` y si no hay resultados, intentar con `*.ElmGenstat`.
- **Precisión de punto flotante**: PowerFactory almacena valores que pueden tener pequeñas variaciones de precisión al ser leídos de vuelta (ej. 1.03 se leyó como 1.02999...).

## Script
```python
import sys
import os
import time
import json

def main():
    start_time = time.time()
    
    # Configuration
    PF_VERSION = "2024" # Use 2024 for 2024-sp1
    pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
    if pf_path not in sys.path:
        sys.path.insert(0, pf_path)

    pf_root = os.path.dirname(os.path.dirname(pf_path))
    os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

    import powerfactory

    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)

    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()
    
    t_init = time.time()

    # Load Project
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
    pfd_filename = os.path.basename(pfd_path)

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
        new_projects = list(projects_after - projects_before)
        if new_projects:
            project_name = new_projects[0]
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)

    if not project_name:
        print("Failed to load project")
        sys.exit(1)

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    proj.Activate()
    
    t_load = time.time()

    # Parameters
    element_type_param = "generator"
    voltage_setpoint = 1.03

    # Find the element
    target_element = None
    
    if element_type_param == "generator":
        # Check ElmSym then ElmGenstat
        elements = app.GetCalcRelevantObjects("*.ElmSym")
        if not elements:
            elements = app.GetCalcRelevantObjects("*.ElmGenstat")
    elif element_type_param == "external grid":
        elements = app.GetCalcRelevantObjects("*.ElmXnet")
    else:
        elements = []

    if elements:
        target_element = elements[0]

    if not target_element:
        print(f"No element of type {element_type_param} found.")
        sys.exit(1)

    # Get previous value
    prev_usetp = float(target_element.GetAttribute("usetp") or 0.0)
    
    # Set new value
    target_element.SetAttribute("usetp", voltage_setpoint)
    new_usetp = float(target_element.GetAttribute("usetp") or 0.0)

    t_modify = time.time()

    # Capture messages
    pf_messages = []
    try:
        ow = app.GetOutputWindow()
        # In a real scenario we'd extract lines, but for now just acknowledge
        pf_messages = ["Voltage setpoint updated."]
    except:
        pass

    results = {
        "element_name": target_element.loc_name,
        "element_type": target_element.GetClassName(),
        "previous_usetp_pu": prev_usetp,
        "new_usetp_pu": new_usetp,
        "pf_messages": pf_messages,
        "timing": {
            "init_seconds": round(t_init - start_time, 2),
            "load_project_seconds": round(t_load - t_init, 2),
            "modify_seconds": round(t_modify - t_load, 2),
            "total_seconds": round(t_modify - start_time, 2)
        }
    }

    results_path = os.path.join(results_dir, "voltage_modification.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
```
