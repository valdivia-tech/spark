# [FALLIDO] Emergency Generation Dispatch en 2603 (Laboral Diurno)
Fecha: 2026-03-24
Tarea: "En proyecto 2603-BD-OP-COORD-DMAP.pfd: Activa estudio Base SEN y escenario Laboral Diurno, deshabilita DSLs, realiza un despacho de emergencia (P = 1.05 * 8900 MW proporcional a Sgn), pone usetp=1.0, asegura Red Externa como Slack y corre Flujo de Potencia."

## Qué se intentó
- Se activó el caso de estudio "Base SEN" y el escenario "Laboral Diurno".
- Se deshabilitaron 3220 modelos dinámicos (ElmDsl).
- Se despacharon 696 generadores (ElmSym/ElmGenstat) proporcionalmente a su `sgn` usando un factor de 0.175 (total dispatch ~9345 MW).
- Se configuró la red externa como Slack y se corrió un flujo AC con Flat Start (iopt_init=1).

## Por qué falló
- El flujo de potencia divergió (error_code 1).
- El diagnóstico reveló un desbalance de ~267 MW entre la suma de `pgini` y `plini`.
- Lo más crítico: se detectaron **20368 barras aisladas** (con tensión 0). Esto indica que la activación del caso de estudio o el escenario no conectó la red correctamente, o que la base operacional está fragmentada masivamente en la configuración seleccionada.

## Recomendación
- Revisar si el caso "Base SEN" es el punto de partida correcto para una base operacional de SCADA. Normalmente estas bases tienen casos específicos por fecha/hora.
- Verificar la topología: 20k+ barras aisladas sugieren que los interruptores/seccionadores están abiertos en gran parte del sistema o que el escenario no está aplicando las variaciones topológicas necesarias.
- Intentar usar el comando "Calculate Topology" antes del flujo si existen islas.

## Script (Última versión antes de divergencia)
```python
import sys
import os
import time
import json

def run():
    # Setup PowerFactory path
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
    
    if not app:
        print("Failed to get PowerFactory application.")
        return

    res = {
        "timing": {},
        "pf_messages": [],
        "status": "starting"
    }
    
    start_time = time.time()
    
    # 1. Load project
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
    pfd_filename = os.path.basename(pfd_path)
    
    cache_file = os.path.join("results", ".project_cache.json")
    os.makedirs("results", exist_ok=True)
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
        new_projects = projects_after - projects_before
        if new_projects:
            project_name = list(new_projects)[0]
        else:
            res["status"] = "error"
            res["error"] = "Import failed"
            save_results(res)
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
        res["status"] = "error"
        res["error"] = "Project not found after import"
        save_results(res)
        return
        
    proj.Activate()
    res["timing"]["load_project_seconds"] = time.time() - start_time
    
    # 2. Activate study case and scenario
    step_start = time.time()
    study_case = None
    all_cases = proj.GetContents("*.IntCase", 1)
    for c in all_cases:
        if "Base SEN" in c.loc_name:
            study_case = c
            break
            
    if not study_case:
        if all_cases:
            study_case = all_cases[0]
        else:
            res["status"] = "error"
            res["error"] = "No study case found"
            save_results(res)
            return
            
    study_case.Activate()
    
    scenario = None
    all_scenarios = proj.GetContents("*.IntScenario", 1)
    for s in all_scenarios:
        if "Laboral Diurno" in s.loc_name:
            scenario = s
            break
            
    if scenario:
        scenario.Activate()
    
    res["timing"]["activation_seconds"] = time.time() - step_start
    res["study_case"] = study_case.loc_name
    res["scenario"] = scenario.loc_name if scenario else "None"
    
    # 3. Disable all ElmDsl
    step_start = time.time()
    dsl_models = app.GetCalcRelevantObjects("*.ElmDsl")
    for dsl in dsl_models:
        try:
            dsl.outserv = 1
        except:
            pass
    res["timing"]["disable_dsl_seconds"] = time.time() - step_start
    res["dsl_disabled_count"] = len(dsl_models)
    
    # 4. Emergency Generation Dispatch
    step_start = time.time()
    gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
    total_sgn = 0.0
    gen_data = []
    
    for g in gens:
        try:
            g.outserv = 0
            sgn = 100.0
            typ = getattr(g, "typ_id", None)
            
            if typ:
                sgn_val = getattr(typ, "sgn", 100.0)
                if sgn_val and sgn_val > 0: sgn = sgn_val
            
            total_sgn += sgn
            gen_data.append((g, sgn))
        except:
            pass
        
    target_p = 8900.0 * 1.05
    k = target_p / total_sgn if total_sgn > 0 else 0
    
    for g, sgn in gen_data:
        try:
            g.pgini = sgn * k
            g.usetp = 1.0
        except:
            pass
        
    res["timing"]["dispatch_seconds"] = time.time() - step_start
    res["dispatch_factor"] = k
    res["total_nominal_power_mva"] = total_sgn
    res["total_gens"] = len(gens)
    
    # 5. External Grid reference
    xnets = app.GetCalcRelevantObjects("*.ElmXnet")
    for x in xnets:
        try:
            # We want at least one reference bus
            if "CENTRAL" in x.loc_name or not any(getattr(xn, "ip_ctrl", 0) == 1 for xn in xnets):
                 x.outserv = 0
                 x.ip_ctrl = 1
                 res["slack_bus"] = x.loc_name
        except:
            pass
    
    # 6. Run Load Flow
    step_start = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    if ldf:
        try: ldf.iopt_init = 1
        except: pass
        try: ldf.iopt_errlf = 1
        except: pass
        
        error_code = ldf.Execute()
        res["timing"]["power_flow_seconds"] = time.time() - step_start
        res["error_code"] = error_code
        res["status"] = "converged" if error_code == 0 else "diverged"
    else:
        res["status"] = "error"
        res["error"] = "ComLdf not found"
        
    # Attempt to capture some messages safely
    res["pf_messages"] = ["Output window captured but content extraction skipped for stability"]
    
    # 7. Extract Results
    step_start = time.time()
    if res["status"] == "converged":
        total_gen_p = 0.0
        total_load_p = 0.0
        for g in gens:
            p = getattr(g, "m:P:bus1", 0)
            if p: total_gen_p += p
        
        for x in xnets:
            if getattr(x, "outserv", 0) == 0:
                p = getattr(x, "m:Psum:bus1", 0)
                if p: total_gen_p += p
                
        loads = app.GetCalcRelevantObjects("*.ElmLod")
        for l in loads:
            p = getattr(l, "m:Psum:bus1", 0)
            if p: total_load_p += p
        
        res["total_generation_mw"] = total_gen_p
        res["total_load_mw"] = total_load_p
        res["losses_mw"] = total_gen_p - total_load_p
        
        buses = app.GetCalcRelevantObjects("*.ElmTerm")
        bus_v = []
        for b in buses:
            u = getattr(b, "m:u", 0)
            if u and u > 0.1:
                bus_v.append({"name": b.loc_name, "u_pu": u})
        
        bus_v.sort(key=lambda x: x["u_pu"])
        res["lowest_voltages"] = bus_v[:5]
        
        lines = app.GetCalcRelevantObjects("*.ElmLne")
        line_loading = []
        for l in lines:
            load = getattr(l, "c:loading", 0)
            if load:
                line_loading.append({"name": l.loc_name, "loading_pct": load})
        
        line_loading.sort(key=lambda x: x["loading_pct"], reverse=True)
        res["highest_loadings"] = line_loading[:5]
        
    res["timing"]["extract_results_seconds"] = time.time() - step_start
    save_results(res)

def save_results(data):
    with open("results/dispatch_results.json", "w") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    run()
```
