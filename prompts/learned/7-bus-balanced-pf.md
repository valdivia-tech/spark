# Flujo de Potencia Balancedo AC — 7-bus.pfd
Fecha: 2026-05-21
Tarea: "Correr flujo de potencia AC en 7-bus.pfd con ajustes automáticos y limites de reactivo"

## Lecciones aprendidas
- **JSON Serialization**: `app.GetOutputWindow()` devuelve un objeto `OutputWindow` que no es serializable. Usar `str(ow)` o extraer contenido si es necesario.
- **Totales**: El modelo 7-bus usa una Red Externa (`ElmXnet`) para la generación, por lo que `total_gen_mw` puede ser 0 si solo se cuentan generadores síncronos/estáticos. Siempre sumar `ElmXnet` por separado.
- **Estabilidad de parámetros**: Los parámetros `iopt_at=1`, `iopt_asht=1`, `iopt_lim=1` funcionan correctamente en este modelo didáctico.

## Script
```python
import sys, os, json, time

def run():
    t_start = time.time()
    timing = {}

    # 1. Initialize PowerFactory
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
    
    timing["init_seconds"] = time.time() - t_start
    t_load = time.time()

    RESULTS_DIR = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

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

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    
    if not proj:
        for p in (user.GetContents("*.IntPrj") or []):
            if "7-bus" in p.loc_name or "Taller 2" in p.loc_name:
                proj = p
                project_name = p.loc_name
                break
                
    if not proj:
        return

    proj.Activate()
    timing["load_project_seconds"] = time.time() - t_load
    
    # 3. Activate study case
    t_pf_prep = time.time()
    study_cases = proj.GetContents("*.IntCase", 1)
    if study_cases:
        study_cases[0].Activate()
    
    # 4. Configure and run load flow
    ldf = app.GetFromStudyCase("ComLdf")
    if ldf is None:
        sc = app.GetActiveStudyCase()
        if sc:
            ldf = sc.CreateObject('ComLdf', 'LoadFlow')

    if ldf:
        ldf.iopt_net = 0      # AC
        ldf.iopt_at = 1       # Auto tap
        ldf.iopt_asht = 1     # Auto shunt
        ldf.iopt_sim = 0      # Balanced
        ldf.iopt_lim = 1      # Reactive limits
        error_code = ldf.Execute()
    else:
        error_code = -1

    timing["power_flow_seconds"] = time.time() - t_pf_prep
    t_extract = time.time()

    # 5. Extract results
    results = {
        "project": project_name,
        "status": "converged" if error_code == 0 else "diverged" if error_code == 1 else "error",
        "error_code": error_code,
        "pf_messages": str(app.GetOutputWindow()),
        "timing": timing
    }

    if error_code == 0:
        bus_data = {}
        v_pu_list = []
        for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
            if bus.HasAttribute("m:u"):
                u_pu = float(bus.GetAttribute("m:u") or 0)
                v_pu_list.append(u_pu)
                bus_data[bus.loc_name] = {
                    "v_pu": round(u_pu, 4),
                    "v_kv": round(float(bus.GetAttribute("m:U") or 0), 2),
                    "angle_deg": round(float(bus.GetAttribute("m:phiu") or 0), 2)
                }
        results["buses"] = bus_data
        results["min_v_pu"] = round(min(v_pu_list), 4) if v_pu_list else 0
        results["max_v_pu"] = round(max(v_pu_list), 4) if v_pu_list else 0

        line_data = {}
        for line in app.GetCalcRelevantObjects("*.ElmLne"):
            if line.HasAttribute("c:loading"):
                line_data[line.loc_name] = {
                    "loading_pct": round(float(line.GetAttribute("c:loading") or 0), 2)
                }
        results["lines"] = line_data

        trafo_data = {}
        for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
            if trafo.HasAttribute("c:loading"):
                trafo_data[trafo.loc_name] = {
                    "loading_pct": round(float(trafo.GetAttribute("c:loading") or 0), 2)
                }
        results["transformers"] = trafo_data

        total_gen_mw = 0.0
        total_ext_mw = 0.0
        total_load_mw = 0.0
        
        for g in app.GetCalcRelevantObjects("*.ElmSym"):
            if g.outserv == 0 and g.HasAttribute("m:P:bus1"):
                total_gen_mw += float(g.GetAttribute("m:P:bus1") or 0)
        
        for g in app.GetCalcRelevantObjects("*.ElmGenstat"):
            if g.outserv == 0 and g.HasAttribute("m:P:bus1"):
                total_gen_mw += float(g.GetAttribute("m:P:bus1") or 0)

        for x in app.GetCalcRelevantObjects("*.ElmXnet"):
            if x.outserv == 0 and x.HasAttribute("m:P:bus1"):
                total_ext_mw += float(x.GetAttribute("m:P:bus1") or 0)

        for l in app.GetCalcRelevantObjects("*.ElmLod"):
            if l.outserv == 0 and l.HasAttribute("m:P:bus1"):
                total_load_mw += abs(float(l.GetAttribute("m:P:bus1") or 0))

        results["totals"] = {
            "gen_mw": round(total_gen_mw, 2),
            "ext_grid_mw": round(total_ext_mw, 2),
            "load_mw": round(total_load_mw, 2),
            "losses_mw": round(total_gen_mw + total_ext_mw - total_load_mw, 2)
        }

    timing["extract_results_seconds"] = time.time() - t_extract
    timing["total_seconds"] = time.time() - t_start

    with open(os.path.join(RESULTS_DIR, "power_flow_results.json"), "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run()
```
