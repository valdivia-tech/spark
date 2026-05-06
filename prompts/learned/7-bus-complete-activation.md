# Flujo de potencia 7-bus con activación de elementos out-of-service
Fecha: 2026-04-07
Tarea: "Activa el proyecto 'projects/7-bus.pfd'. Activa todos los elementos que estén fuera de servicio. Ejecuta un flujo de potencia. Extrae los resultados de todas las barras y líneas."

## Lecciones aprendidas
- Para activar elementos que están fuera de servicio (`outserv = 1`), es mejor buscarlos usando `proj.GetContents(pattern, 1)` (el argumento 1 indica búsqueda recursiva) en lugar de `app.GetCalcRelevantObjects()`, ya que esta última función suele omitir objetos fuera de servicio.
- Al extraer tensiones de barras, el atributo `m:u` suele representar el valor en p.u. y `m:U` el valor en kV, aunque esto puede variar según la configuración del proyecto.
- Para la serialización de `pf_messages`, la captura del `OutputWindow` puede ser compleja si no se conocen los métodos exactos de la versión; usar un bloque `try-except` con múltiples métodos (`GetCount`/`GetMessage` o `GetLineCount`/`GetLineText`) es la estrategia más robusta.

## Script
```python
import sys
import os
import time
import json

def run():
    # 1. Initialization
    pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
    if pf_path not in sys.path:
        sys.path.insert(0, pf_path)

    pf_root = os.path.dirname(os.path.dirname(pf_path))
    os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

    try:
        import powerfactory
        app = powerfactory.GetApplication()
    except:
        try:
            import powerfactory
            app = powerfactory.GetApplicationExt(None, None)
        except Exception as e:
            print(f"Failed to get PowerFactory application: {e}")
            return
    
    if not app:
        print("Failed to get PowerFactory application.")
        return

    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    timing = {}
    
    # 2. Load project
    start_time = time.time()
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
    pfd_filename = os.path.basename(pfd_path)

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
        else:
            project_name = "7-bus"

        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    
    if not proj:
        for p in (user.GetContents("*.IntPrj") or []):
            if "7-bus" in p.loc_name or "Taller" in p.loc_name:
                proj = p
                project_name = p.loc_name
                break
    
    if not proj:
        print(f"Could not find project {project_name}")
        return

    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time

    # 3. Activate elements
    start_time = time.time()
    patterns = ["*.ElmSym", "*.ElmGenstat", "*.ElmLod", "*.ElmTr2", "*.ElmLne", "*.ElmXnet"]
    activated_count = 0
    
    # Buscamos todos los elementos en el proyecto recursivamente
    for pattern in patterns:
        objs = proj.GetContents(pattern, 1)
        for obj in objs:
            if obj.outserv == 1:
                obj.outserv = 0
                activated_count += 1
    
    timing["activate_elements_seconds"] = time.time() - start_time

    # 4. Power Flow
    start_time = time.time()
    study_case = app.GetActiveStudyCase()
    if study_case is None:
        study_cases = proj.GetContents("*.IntCase", 1)
        if study_cases:
            study_case = study_cases[0]
            study_case.Activate()
        else:
            sc_folder = proj.GetContents("Network Model/Study Cases")[0] if proj.GetContents("Network Model/Study Cases") else proj
            study_case = sc_folder.CreateObject("IntCase", "Study Case")
            study_case.Activate()

    ldf = app.GetFromStudyCase("ComLdf")
    if ldf:
        ldf.iopt_net = 0
        error_code = ldf.Execute()
    else:
        error_code = -1
    
    timing["power_flow_seconds"] = time.time() - start_time
    
    # Capture output window safely
    output_messages = []
    ow = app.GetOutputWindow()
    if ow:
        try:
            for i in range(ow.GetCount()):
                output_messages.append(str(ow.GetMessage(i)))
        except:
            try:
                for i in range(ow.GetLineCount()):
                    output_messages.append(ow.GetLineText(i))
            except:
                output_messages = [str(ow)]

    # 5. Extract results
    start_time = time.time()
    buses = []
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        v_kv = bus.GetAttribute("m:U")
        v_pu = bus.GetAttribute("m:u")
        buses.append({
            "name": bus.loc_name,
            "m:u (kV)": v_kv,
            "m:u:pu (p.u.)": v_pu
        })

    lines = []
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        lines.append({
            "name": line.loc_name,
            "m:loading (%)": line.GetAttribute("m:loading")
        })

    # Summary: Pgen (MW), Pload (MW), Ploss (MW)
    p_gen = 0.0
    for g in app.GetCalcRelevantObjects("*.ElmSym"):
        p_gen += (g.GetAttribute("m:P:bus1") or 0.0)
    for g in app.GetCalcRelevantObjects("*.ElmGenstat"):
        p_gen += (g.GetAttribute("m:P:bus1") or 0.0)
    for x in app.GetCalcRelevantObjects("*.ElmXnet"):
        p_gen += (x.GetAttribute("m:P:bus1") or 0.0)

    p_load = 0.0
    for l in app.GetCalcRelevantObjects("*.ElmLod"):
        p_load += (l.GetAttribute("m:P:bus1") or 0.0)

    p_loss = p_gen - p_load

    timing["extract_results_seconds"] = time.time() - start_time

    results = {
        "status": "success" if error_code == 0 else "failed",
        "error_code": error_code,
        "activated_elements": activated_count,
        "summary": {
            "p_gen_mw": p_gen,
            "p_load_mw": p_load,
            "p_loss_mw": p_loss
        },
        "buses": buses,
        "lines": lines,
        "timing": timing,
        "pf_messages": output_messages
    }

    output_file = os.path.join(results_dir, "power_flow_7bus_complete.json")
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run()
```
