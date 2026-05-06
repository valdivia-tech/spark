# Benchmark de rendimiento en Proyecto 2603

Fecha: 2026-04-09
Tarea: "Ejecuta este benchmark de rendimiento. Escribe UN SOLO script de Python que haga todo lo siguiente: 1. Importa el proyecto 2603... 2. Activa study case y escenario... 3. Configura ComLdf... 4. Warm-up... 5. Loop 25 flujos... 6. Extrae verificación... 7. Guarda resultados..."

## Lecciones aprendidas
- Importación de `powerfactory` debe realizarse **después** de manipular `sys.path` y `os.environ['PATH']` para evitar fallos si el módulo no está en el site-packages estándar.
- El objeto `ComLdf` puede tener comportamientos inconsistentes con `SetAttribute` en algunas instalaciones; el uso de `hasattr(obj, attr)` y `setattr(obj, attr, val)` como fallback es una estrategia robusta.
- `app.GetOutputWindow()` devuelve un objeto `OutputWindow` que no es directamente serializable a JSON. Se debe convertir a `str()` o iterar sobre sus líneas.
- En bases de operación del CEN (como la 2603), la activación del Study Case y el Escenario es suficiente para configurar el despacho, pero los nombres deben coincidir exactamente ("Base SEN" y "Laboral Diurno").

## Script
```python
import sys
import os
import time
import json

def run_benchmark():
    # 1. Initialization
    pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
    if pf_path not in sys.path:
        sys.path.insert(0, pf_path)
    
    pf_root = os.path.dirname(os.path.dirname(pf_path))
    os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

    import powerfactory

    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()

    if not app:
        print("Could not initialize PowerFactory.")
        return

    # Results directory
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)

    # 2. Load Project (with cache)
    t0_load = time.time()
    user = app.GetCurrentUser()
    # Path to the project
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
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
    
    if not proj:
        print(f"Project {project_name} not found.")
        return
    
    proj.Activate()
    t_load = time.time() - t0_load

    # 3. Activation (Study Case and Scenario)
    t0_activate = time.time()
    
    # Find Study Case "Base SEN"
    study_case = None
    all_cases = proj.GetContents("*.IntCase", 1)
    for sc in all_cases:
        if sc.loc_name == "Base SEN":
            study_case = sc
            break
    
    if study_case:
        study_case.Activate()
    else:
        # Try to find by partial match
        for sc in all_cases:
            if "Base SEN" in sc.loc_name:
                study_case = sc
                study_case.Activate()
                break
    
    # Find Scenario "Laboral Diurno"
    scenarios = proj.GetContents("*.IntScenario", 1)
    for scn in scenarios:
        if scn.loc_name == "Laboral Diurno":
            scn.Activate()
            break
    
    t_activate = time.time() - t0_activate

    # 4. Configuration
    ldf = app.GetFromStudyCase("ComLdf")
    
    # Try setting attributes with direct access and HasAttribute
    attrs_to_set = {"iopt_init": 1, "iopt_pbal": 4, "iopt_errlf": 1}
    for attr, val in attrs_to_set.items():
        if hasattr(ldf, attr):
            setattr(ldf, attr, val)
        elif ldf.HasAttribute(attr):
            ldf.SetAttribute(attr, val)

    # 5. Warm-up
    for _ in range(2):
        err = ldf.Execute()
        if err != 0:
            print(f"Warm-up failed with error code {err}")
            results = {
                "status": "failed",
                "error_code": int(err),
                "pf_messages": str(app.GetOutputWindow())
            }
            with open(os.path.join(results_dir, "benchmark_results.json"), "w") as f:
                json.dump(results, f, indent=2)
            return

    # 6. Benchmarking Loop
    individual_times = []
    t0_loop = time.time()
    for _ in range(25):
        t_start = time.perf_counter()
        ldf.Execute()
        t_end = time.perf_counter()
        individual_times.append(t_end - t_start)
    t_loop_total = time.time() - t0_loop

    # 7. Verification Data (EXACT CODE PROVIDED)
    gen_mw = 0.0
    for g in app.GetCalcRelevantObjects("*.ElmSym"):
        if g.GetAttribute("outserv") == 0 and g.HasAttribute("m:P:bus1"):
            v = g.GetAttribute("m:P:bus1")
            if v is not None: gen_mw += v
    for g in app.GetCalcRelevantObjects("*.ElmGenstat"):
        if g.GetAttribute("outserv") == 0 and g.HasAttribute("m:P:bus1"):
            v = g.GetAttribute("m:P:bus1")
            if v is not None: gen_mw += v

    load_mw = 0.0
    for ld in app.GetCalcRelevantObjects("*.ElmLod"):
        if ld.GetAttribute("outserv") == 0 and ld.HasAttribute("m:P:bus1"):
            v = ld.GetAttribute("m:P:bus1")
            if v is not None: load_mw += v

    v_navia = 0.0
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        if "NAVIA" in bus.loc_name.upper() and "500" in bus.loc_name:
            if bus.HasAttribute("m:u"):
                v_navia = bus.GetAttribute("m:u") or 0.0
                break

    # 8. Save results
    avg_flow = sum(individual_times) / len(individual_times) if individual_times else 0.0
    
    results = {
      "times_breakdown": {
          "load_sec": float(t_load), 
          "activation_sec": float(t_activate), 
          "total_solver_loop_sec": float(t_loop_total)
      },
      "individual_flow_times": [float(t) for t in individual_times],
      "avg_flow_time_sec": float(avg_flow),
      "verification_data": {
          "gen_total_mw": float(gen_mw), 
          "load_total_mw": float(abs(load_mw)), 
          "v_cerro_navia_pu": float(v_navia)
      },
      "pf_messages": str(app.GetOutputWindow())
    }

    with open(os.path.join(results_dir, "benchmark_results.json"), "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_benchmark()
```
