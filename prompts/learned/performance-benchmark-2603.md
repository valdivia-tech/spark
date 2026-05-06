# Benchmark de Rendimiento VM - Proyecto 2603

Fecha: 2026-04-09
Tarea: "BENCHMARK DE RENDIMIENTO VM - PROYECTO 2603"

## Lecciones aprendidas
- **Localización de Proyecto**: El archivo .pfd se encuentra en una subcarpeta `../projects/2603/`, lo cual requiere una ruta específica para el objeto `CompfdImport`.
- **Configuración de Solver**: La combinación de `iopt_init=1` (Flat Start) y `iopt_pbal=4` (Distributed Slack) es robusta para sistemas grandes como el SEN chileno (2603 buses).
- **Atributos de Verificación**: Para bases de operación del CEN, los valores de despacho se encuentran en `pgini` y `plini`, mientras que los resultados post-flujo se encuentran en variables de monitoreo (`m:u`).
- **Rendimiento**: El tiempo de ejecución del flujo de potencia en este entorno se estabiliza después de los ciclos de warm-up, permitiendo una medición precisa del rendimiento del solver.

## Script
```python
import sys
import os
import time
import json

def run_benchmark():
    # Setup and PF Init
    pf_paths = [
        os.environ.get("POWERFACTORY_PATH"),
        r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12",
        r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14"
    ]
    
    app = None
    for pf_path in pf_paths:
        if not pf_path: continue
        if pf_path not in sys.path:
            sys.path.insert(0, pf_path)
        
        pf_root = os.path.dirname(os.path.dirname(pf_path))
        os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

        try:
            import powerfactory
            app = powerfactory.GetApplication()
            if app: break
            app = powerfactory.GetApplicationExt(None, None)
            if app: break
        except:
            continue
    
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
        "pf_messages": [],
        "timing": {}
    }

    t0_script = time.time()
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
    pfd_filename = os.path.basename(pfd_path)

    # 1. Project Load Time
    t_start_load = time.perf_counter()
    
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
    
    t_end_load = time.perf_counter()
    t_load = t_end_load - t_start_load
    results["times_breakdown"]["load_sec"] = t_load
    results["timing"]["load_project_seconds"] = t_load

    # 2. Activation Time (Project + Scenario)
    t_start_activate = time.perf_counter()
    proj.Activate()
    
    scenarios = proj.GetContents("*.IntScenario", 1)
    target_scenario = None
    for scn in scenarios:
        if scn.loc_name == "Laboral Diurno":
            target_scenario = scn
            break
    
    if target_scenario:
        target_scenario.Activate()
    else:
        study_cases = proj.GetContents("*.IntCase", 1)
        for sc in study_cases:
            if sc.loc_name == "Laboral Diurno":
                sc.Activate()
                break
    
    t_end_activate = time.perf_counter()
    t_activate = t_end_activate - t_start_activate
    results["times_breakdown"]["activation_sec"] = t_activate
    results["timing"]["activation_seconds"] = t_activate

    # 3. Solver Config
    ldf = app.GetFromStudyCase("ComLdf")
    if not ldf:
        study_case = app.GetActiveStudyCase()
        if study_case:
            ldf = study_case.CreateObject("ComLdf", "LDF")
    
    if not ldf:
        print("Could not find or create ComLdf.")
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
    t_start_loop = time.perf_counter()
    for i in range(25):
        t0 = time.perf_counter()
        ldf.Execute()
        t1 = time.perf_counter()
        results["individual_flow_times"].append(t1 - t0)
    
    t_end_loop = time.perf_counter()
    total_loop_sec = t_end_loop - t_start_loop
    results["times_breakdown"]["total_solver_loop_sec"] = total_loop_sec
    results["avg_flow_time_sec"] = sum(results["individual_flow_times"]) / 25
    results["timing"]["benchmark_loop_seconds"] = total_loop_sec

    # 6. Verification Data
    total_gen_mw = 0.0
    for gen in app.GetCalcRelevantObjects("*.ElmSym"):
        if gen.outserv == 0:
            p = gen.GetAttribute("pgini")
            if p is not None: total_gen_mw += p

    for gstat in app.GetCalcRelevantObjects("*.ElmGenstat"):
        if gstat.outserv == 0:
            p = gstat.GetAttribute("pgini")
            if p is not None: total_gen_mw += p

    total_load_mw = 0.0
    for load in app.GetCalcRelevantObjects("*.ElmLod"):
        if load.outserv == 0:
            p = load.GetAttribute("plini")
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
    
    results["timing"]["total_script_seconds"] = time.time() - t0_script
    
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
