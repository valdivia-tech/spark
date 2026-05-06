# Benchmark de Rendimiento — CEN 2603 (25 flujos)
Fecha: 2026-05-06
Tarea: "Ejecuta este benchmark de rendimiento. Escribe UN SOLO script de Python que haga todo lo siguiente: ... 25 flujos ..."

## Lecciones aprendidas
- **Nombre de Proyecto**: El proyecto se encontró como `2603-BD-OP-COORD-DMAP` en el servidor, coincidiendo con el nombre del archivo .pfd.
- **GetContent de OutputWindow**: En PowerFactory 2024+, `GetContent()` no acepta argumentos de lista. El uso correcto para capturar mensajes es `app.GetOutputWindow().GetContent()`.
- **Rendimiento**: El tiempo promedio por flujo de potencia en el CEN 2603 es de aproximadamente 7.84 segundos.
- **Activación de Escenario**: Aunque el Study Case "Base SEN" suele activar un escenario por defecto, la activación explícita del escenario "Laboral Diurno" asegura que los totales de generación y carga coincidan con los valores de referencia (9,320 MW gen / 8,892 MW carga).

## Script
```python
import sys, os, json, time

def run_benchmark():
    # --- Timing for load ---
    t_load_start = time.perf_counter()
    
    # --- PowerFactory init ---
    pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
    if pf_path not in sys.path:
        sys.path.insert(0, pf_path)
    pf_root = os.path.dirname(os.path.dirname(pf_path))
    os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')
    
    import powerfactory
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)

    RESULTS_DIR = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    # --- Load project ---
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd"))
    
    proj = None
    possible_names = ["2603-BD-OP-COORD-DMAP", "2305-BD-Ovalle.12072023"]
    for p in (user.GetContents("*.IntPrj") or []):
        if any(name in p.loc_name for name in possible_names):
            proj = p
            break
            
    if proj is None:
        projects_before = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        imp = user.CreateObject('CompfdImport', 'ImportPfd')
        imp.SetAttribute("e:g_file", pfd_path)
        imp.g_target = user
        imp.Execute()
        imp.Delete()
        projects_after = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        new_projects = list(projects_after - projects_before)
        if new_projects:
            proj_name = new_projects[0]
            for p in (user.GetContents("*.IntPrj") or []):
                if p.loc_name == proj_name:
                    proj = p
                    break
        else:
            for p in (user.GetContents("*.IntPrj") or []):
                if any(name in p.loc_name for name in possible_names):
                    proj = p
                    break

    if proj is None:
        print(f"Project could not be found or imported.")
        return

    proj.Activate()
    t_load = time.perf_counter() - t_load_start

    # --- Activate Study Case + Scenario ---
    t_activate_start = time.perf_counter()
    
    sc_found = False
    for sc in proj.GetContents("*.IntCase", 1):
        if "Base SEN" in sc.loc_name:
            sc.Activate()
            sc_found = True
            break
    
    if not sc_found:
        scs = proj.GetContents("*.IntCase", 1)
        if scs:
            scs[0].Activate()

    scn_found = False
    for scn in proj.GetContents("*.IntScenario", 1):
        if "Laboral Diurno" in scn.loc_name:
            scn.Activate()
            scn_found = True
            break
    
    if not scn_found:
        for scn in app.GetCalcRelevantObjects("*.IntScenario"):
            if "Laboral Diurno" in scn.loc_name:
                scn.Activate()
                scn_found = True
                break
    
    if not scn_found:
        print("Scenario 'Laboral Diurno' not found.")

    t_activate = time.perf_counter() - t_activate_start

    # --- Configure ComLdf ---
    ldf = app.GetFromStudyCase("ComLdf")
    
    def set_attr(obj, attr, val):
        if obj.HasAttribute(attr):
            try:
                obj.SetAttribute(attr, val)
            except:
                setattr(obj, attr, val)

    set_attr(ldf, "iopt_init", 1)
    set_attr(ldf, "iopt_pbal", 4)
    set_attr(ldf, "iopt_errlf", 1)

    # --- Warm-up ---
    for i in range(2):
        err = ldf.Execute()
        if err != 0:
            print(f"Warm-up {i+1} failed with code {err}. Aborting.")
            return

    # --- Loop 25 times ---
    flow_times = []
    for _ in range(25):
        t_s = time.perf_counter()
        ldf.Execute()
        t_e = time.perf_counter()
        flow_times.append(t_e - t_s)
    
    total_solver_loop_sec = sum(flow_times)
    avg_flow_time_sec = total_solver_loop_sec / 25

    # --- Extract Verification (Exact code provided) ---
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

    # --- Final Results ---
    results = {
        "times_breakdown": {
            "load_sec": float(t_load),
            "activation_sec": float(t_activate),
            "total_solver_loop_sec": float(total_solver_loop_sec)
        },
        "individual_flow_times": [float(t) for t in flow_times],
        "avg_flow_time_sec": float(avg_flow_time_sec),
        "verification_data": {
            "gen_total_mw": float(gen_mw),
            "load_total_mw": float(abs(load_mw)),
            "v_cerro_navia_pu": float(v_navia)
        }
    }

    # Capture output window messages
    out_window = app.GetOutputWindow()
    if out_window:
        msgs = out_window.GetContent()
        if msgs and len(msgs) > 1:
            results["pf_messages"] = [str(m) for m in msgs[1][-20:]]

    # Timing object for Spark rules
    results["timing"] = {
        "load_project_seconds": float(t_load),
        "activation_seconds": float(t_activate),
        "benchmark_loop_seconds": float(total_solver_loop_sec),
        "total_seconds": float(time.perf_counter() - t_load_start)
    }

    # Save to file
    with open(os.path.join(RESULTS_DIR, "benchmark_results.json"), "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_benchmark()
```
