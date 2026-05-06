# Flujo de Potencia Balancedo AC (PF 2024) — 7-bus.pfd
Fecha: 2026-05-04
Tarea: "Correr flujo de potencia AC en 7-bus.pfd con ajustes automáticos, limites de reactivo y corrección de tensión PF 2024"

## Lecciones aprendidas
- **PowerFactory 2024 SP1 Quirk**: El atributo `m:U` en terminales devuelve la tensión fase-neutro. Para obtener la tensión fase-fase (`v_kv`), es necesario multiplicar por $\sqrt{3}$ (~1.7320508).
- **Nombre del proyecto**: Al importar `7-bus.pfd`, el proyecto se crea como "Taller 2". Esto es crítico si se busca el proyecto por nombre después de la importación.
- **Configuración de ComLdf**: Se usaron los flags `iopt_net=0`, `iopt_at=1`, `iopt_asht=1`, `iopt_sim=0`, `iopt_lim=1`.
- **Totales**: En este modelo, la Red Externa (`ElmXnet`) actúa como slack, por lo que `total_gen` de máquinas puede ser 0 MW mientras que `ext_grid_mw` suministra la carga.

## Script
```python
import sys, os, json, time, math

def run():
    t_start = time.time()
    timing = {}

    pf_path = r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12"
    if not os.path.exists(pf_path):
        pf_path = os.environ.get("POWERFACTORY_PATH", pf_path)
    
    if pf_path not in sys.path:
        sys.path.insert(0, pf_path)
    
    import powerfactory
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)
    
    if not app:
        print("Could not get PowerFactory application.")
        return

    timing["init_seconds"] = time.time() - t_start
    t_load = time.time()

    RESULTS_DIR = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
    
    # Use the logic from the previous successful run
    projects_before = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
    imp = user.CreateObject('CompfdImport', 'ImportPfd')
    imp.SetAttribute("e:g_file", pfd_path)
    imp.g_target = user
    error = imp.Execute()
    imp.Delete()

    projects_after = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
    new_projects = projects_after - projects_before
    if new_projects:
        project_name = list(new_projects)[0]
    else:
        project_name = next((p for p in reversed(list(projects_after)) if "Taller" in p or "7-bus" in p), None)

    if not project_name:
        print("Project not found.")
        return

    proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
    proj.Activate()
    timing["load_project_seconds"] = time.time() - t_load
    
    t_pf_prep = time.time()
    sc = app.GetActiveStudyCase()
    if not sc:
        study_cases = proj.GetContents("*.IntCase", 1)
        if study_cases:
            study_cases[0].Activate()
            sc = app.GetActiveStudyCase()
        else:
            sc_folder = proj.SearchObject("Study Cases.IntFolder") or proj
            sc = sc_folder.CreateObject('IntCase', 'Study Case')
            sc.Activate()
    
    ldf = app.GetFromStudyCase("ComLdf")
    if ldf is None:
        ldf = sc.CreateObject('ComLdf', 'LoadFlow')

    ldf.iopt_net = 0
    ldf.iopt_at = 1
    ldf.iopt_asht = 1
    ldf.iopt_sim = 0
    ldf.iopt_lim = 1

    error_code = ldf.Execute()
    
    timing["power_flow_seconds"] = time.time() - t_pf_prep
    t_extract = time.time()

    results = {
        "project": proj.loc_name,
        "status": "converged" if error_code == 0 else "diverged" if error_code == 1 else "error",
        "error_code": error_code,
        "pf_messages": str(app.GetOutputWindow().GetContent()),
        "timing": timing
    }

    if error_code == 0:
        bus_data = {}
        v_pu_list = []
        for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
            if bus.HasAttribute("m:u"):
                u_pu = float(bus.GetAttribute("m:u") or 0)
                v_pu_list.append(u_pu)
                v_kv_raw = float(bus.GetAttribute("m:U") or 0)
                # PF 2024 SP1 Quirk: m:U is phase-neutral
                v_kv_ll = v_kv_raw * 1.73205081
                
                bus_data[bus.loc_name] = {
                    "v_pu": round(u_pu, 4),
                    "v_kv": round(v_kv_ll, 2),
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
        # Add 3-winding transformers just in case
        for trafo in app.GetCalcRelevantObjects("*.ElmTr3"):
            if trafo.HasAttribute("c:loading"):
                trafo_data[trafo.loc_name] = {
                    "loading_pct": round(float(trafo.GetAttribute("c:loading") or 0), 2)
                }
        results["transformers"] = trafo_data

        total_gen_mw = 0.0
        total_load_mw = 0.0
        total_ext_mw = 0.0
        
        for g in app.GetCalcRelevantObjects("*.ElmSym"):
            if g.outserv == 0:
                total_gen_mw += float(g.GetAttribute("m:P:bus1") or 0)
        
        for g in app.GetCalcRelevantObjects("*.ElmGenstat"):
            if g.outserv == 0:
                total_gen_mw += float(g.GetAttribute("m:P:bus1") or 0)

        for x in app.GetCalcRelevantObjects("*.ElmXnet"):
            if x.outserv == 0:
                total_ext_mw += float(x.GetAttribute("m:P:bus1") or 0)

        for l in app.GetCalcRelevantObjects("*.ElmLod"):
            if l.outserv == 0:
                total_load_mw += abs(float(l.GetAttribute("m:P:bus1") or 0))

        results["totals"] = {
            "gen_mw": round(total_gen_mw, 2),
            "ext_grid_mw": round(total_ext_mw, 2),
            "load_mw": round(total_load_mw, 2),
            "losses_mw": round(total_gen_mw + total_ext_mw - total_load_mw, 2)
        }

    timing["extract_results_seconds"] = time.time() - t_extract
    timing["total_seconds"] = time.time() - t_start

    output_path = os.path.join(RESULTS_DIR, "run_power_flow_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run()
```
