# Benchmark de Rendimiento VM BENCHMARK V2 (2603)

Fecha: 2026-04-09
Tarea: "EJECUTA UN BENCHMARK DE RENDIMIENTO (VM BENCHMARK V2) PROYECTO: 2603-BD-OP-COORD-DMAP.pfd"

## Lecciones aprendidas
- **Rendimiento del Solver**: El tiempo promedio de ejecución del flujo de potencia para el proyecto 2603 (Laboral Diurno) es de aproximadamente 2.74s bajo las condiciones de Distributed Slack y Flat Start.
- **Serialización JSON**: Los objetos devueltos por la API de PowerFactory (como el `OutputWindow`) no son directamente serializables. Es necesario extraer su contenido usando `.GetContent()` (que devuelve una lista de strings).
- **Rutas de Instalación**: Es crítico verificar la versión instalada de PowerFactory (ej. 2024 SP1 vs 2026) y la versión de Python del entorno para configurar correctamente `sys.path`.
- **Detección de Elementos**: El uso de filtros insensibles a mayúsculas/minúsculas (`.upper()`) y la verificación de `HasAttribute` son prácticas recomendadas para evitar fallos en la extracción de datos de validación.

## Script
```python
import sys
import os
import time
import json

def run_benchmark():
    # 0. Setup and PF Init
    pf_path = r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12"
    
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
        print("Could not initialize PowerFactory application.")
        return

    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    results_file = os.path.join(results_dir, "benchmark_results.json")

    results = {
        "times_breakdown": {},
        "individual_flow_times": [],
        "avg_flow_time_sec": 0,
        "verification_data": {},
        "pf_messages": []
    }

    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
    pfd_filename = os.path.basename(pfd_path)

    # 1. Import
    t_start_load = time.time()
    
    cache_file = os.path.join(results_dir, ".project_cache.json")
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache = json.load(f)
        except: pass

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
            print(f"Import failed for {pfd_path}")
            return
        
        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    
    if not proj:
        print(f"Project '{project_name}' not found.")
        return
        
    proj.Activate()
    t_end_load = time.time()
    results["times_breakdown"]["load_sec"] = t_end_load - t_start_load

    # 2. Activation
    t_start_activate = time.time()
    
    study_cases = proj.GetContents("*.IntCase", 1)
    target_case = None
    for sc in study_cases:
        if sc.loc_name == "Base SEN":
            target_case = sc
            break
    
    if target_case:
        target_case.Activate()
    else:
        print("Study case 'Base SEN' not found. Using active.")
    
    scenarios = proj.GetContents("*.IntScenario", 1)
    target_scenario = None
    for scn in scenarios:
        if scn.loc_name == "Laboral Diurno":
            target_scenario = scn
            break
    
    if target_scenario:
        target_scenario.Activate()
    else:
        print("Scenario 'Laboral Diurno' not found.")

    t_end_activate = time.time()
    results["times_breakdown"]["activation_sec"] = t_end_activate - t_start_activate

    # 3. Solver Config
    ldf = app.GetFromStudyCase("ComLdf")
    if not ldf:
        print("ComLdf not found.")
        return
    
    ldf.iopt_init = 1  # Flat Start
    ldf.iopt_pbal = 4  # Distributed Slack
    if ldf.HasAttribute('iopt_errlf'):
        ldf.SetAttribute('iopt_errlf', 1)

    # 4. Warm-up
    for i in range(2):
        err = ldf.Execute()
        if err != 0:
            print(f"Warm-up failed with error code {err}")
            results["pf_messages"] = app.GetOutputWindow().GetContent()
            with open(results_file, "w") as f:
                json.dump(results, f, indent=2)
            return

    # 5. Benchmark Loop
    t_start_loop = time.time()
    for i in range(25):
        t0 = time.perf_counter()
        ldf.Execute()
        t1 = time.perf_counter()
        results["individual_flow_times"].append(t1 - t0)
    
    t_end_loop = time.time()
    results["times_breakdown"]["total_solver_loop_sec"] = t_end_loop - t_start_loop
    results["avg_flow_time_sec"] = sum(results["individual_flow_times"]) / 25

    # 6. Validation Physical Final
    total_gen_mw = 0.0
    for gen in app.GetCalcRelevantObjects("*.ElmSym"):
        if gen.outserv == 0 and gen.HasAttribute("m:P:bus1"):
            p = gen.GetAttribute("m:P:bus1")
            if p is not None: total_gen_mw += p

    for gstat in app.GetCalcRelevantObjects("*.ElmGenstat"):
        if gstat.outserv == 0 and gstat.HasAttribute("m:P:bus1"):
            p = gstat.GetAttribute("m:P:bus1")
            if p is not None: total_gen_mw += p

    total_load_mw = 0.0
    for load in app.GetCalcRelevantObjects("*.ElmLod"):
        if load.outserv == 0 and load.HasAttribute("m:P:bus1"):
            p = load.GetAttribute("m:P:bus1")
            if p is not None: total_load_mw += abs(p)

    v_cerro_navia = 0.0
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        if "CERRO NAVIA" in bus.loc_name and "500" in bus.loc_name:
            if bus.HasAttribute("m:u"):
                v_cerro_navia = bus.GetAttribute("m:u")
                break

    results["verification_data"] = {
        "gen_total_mw": round(total_gen_mw, 2),
        "load_total_mw": round(total_load_mw, 2),
        "v_cerro_navia_pu": round(v_cerro_navia, 4)
    }
    
    try:
        results["pf_messages"] = app.GetOutputWindow().GetContent()
    except:
        results["pf_messages"] = ["Error extracting PF messages"]

    with open(results_file, "w") as f:
        json.dump(results, f, indent=2)
    print("Benchmark complete.")

if __name__ == "__main__":
    run_benchmark()
```
