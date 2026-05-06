# Extracción Masiva de Datos 2603 (ERNC CC)

Fecha: 2026-04-08
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: Activa Base SEN + escenario ERNC CC, slack distribuido con iopt_errlf=1, NO deshabilites ElmDsl. Corre el flujo y extrae 3 JSON: barras, lineas y generadores."

## Lecciones aprendidas
- **Manejo de Proyectos Grandes**: El proyecto 2603 tiene más de 20,000 barras. La extracción masiva mediante `GetCalcRelevantObjects` y iteración simple es eficiente (~6.5s para 23k+ elementos).
- **Activación de Escenarios**: El escenario solicitado "ERNC CC" se encuentra internamente como "Penetracion ERNC CC". El uso de búsqueda por subcadena es robusto para estos casos.
- **Configuración de ComLdf**: La opción `iopt_pbal=4` activa el Slack Distribuido, lo cual es esencial en sistemas fragmentados (el reporte indica 1343 áreas aisladas).
- **Zonas y Carpetas**: El uso de `obj.GetParent().loc_name` permite obtener una clasificación geográfica o administrativa (zona) basada en la estructura de carpetas del proyecto.

## Script
```python
import sys
import os
import json
import time

# PowerFactory initialization
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def safe_get(obj, attr, default=None):
    try:
        if obj.HasAttribute(attr):
            val = obj.GetAttribute(attr)
            return val if val is not None else default
    except:
        pass
    return default

def get_tech(name):
    name = name.upper()
    if any(name.startswith(k) for k in ["TER", "GEO"]):
        return "Térmica"
    if any(name.startswith(k) for k in ["HE", "HP"]):
        return "Hidráulica"
    if any(name.startswith(k) for k in ["PFV", "CSP"]):
        return "Solar"
    if name.startswith("PE"):
        return "Eólica"
    if name.startswith("BESS"):
        return "Almacenamiento"
    return "Otros"

def get_zone(obj):
    parent = obj.GetParent()
    if parent:
        return parent.loc_name
    return "None"

def run_task():
    start_time = time.time()
    timing = {}
    
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)
        
    if not app:
        return {"error": "Failed to get PowerFactory application"}
    
    # 1. Project loading
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd"))
    
    # Try to find existing project first
    all_projects = user.GetContents("*.IntPrj") or []
    proj = next((p for p in all_projects if "2603" in p.loc_name), None)
    
    if not proj:
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        all_projects = user.GetContents("*.IntPrj") or []
        proj = next((p for p in all_projects if "2603" in p.loc_name), None)

    if not proj:
        return {"error": "Project '2603' not found after import"}
    
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # 2. Activate Study Case 'Base SEN'
    step_start = time.time()
    all_cases = proj.GetContents("*.IntCase", 1)
    study_case = next((c for c in all_cases if "Base SEN" in c.loc_name), None)
    if not study_case:
        return {"error": f"Study case 'Base SEN' not found"}
    study_case.Activate()
    timing["activate_case_seconds"] = time.time() - step_start
    
    # 3. Activate Scenario 'ERNC CC'
    step_start = time.time()
    all_scenarios = proj.GetContents("*.IntScenario", 1) + proj.GetContents("*.ElmScenario", 1)
    scenario = next((s for s in all_scenarios if "ERNC CC" in s.loc_name), None)
    if scenario:
        scenario.Activate()
    timing["activate_scenario_seconds"] = time.time() - step_start
    
    # 4. Load Flow configuration
    step_start = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    if ldf.HasAttribute("iopt_pbal"):
        ldf.SetAttribute("iopt_pbal", 4) # Distributed slack
    if ldf.HasAttribute("iopt_errlf"):
        ldf.SetAttribute("iopt_errlf", 1) # Continue on errors
    
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - step_start
    
    pf_messages = []
    try:
        msg_obj = app.GetOutputWindow()
        if msg_obj:
            pf_messages = msg_obj.GetContent()
    except:
        pass
        
    if error_code != 0:
        all_sym = app.GetCalcRelevantObjects("*.ElmSym")
        all_genstat = app.GetCalcRelevantObjects("*.ElmGenstat")
        all_loads = app.GetCalcRelevantObjects("*.ElmLod") + app.GetCalcRelevantObjects("*.ElmLode")
        
        gen_p = sum(safe_get(g, "pgini", 0.0) for g in all_sym if g.outserv == 0) + \
                sum(safe_get(g, "pini", 0.0) for g in all_genstat if g.outserv == 0)
        load_p = sum(safe_get(l, "plini", 0.0) for l in all_loads if l.outserv == 0)
        
        diag = {
            "status": "diverged",
            "error_code": error_code,
            "project": proj.loc_name,
            "diagnosis": {
                "total_generation_mw": gen_p,
                "total_load_mw": load_p,
                "imbalance_mw": gen_p - load_p,
                "isolated_buses": len([b for b in app.GetCalcRelevantObjects("*.ElmTerm") if safe_get(b, "m:u", 0.0) == 0.0])
            }
        }
        with open(os.path.join(results_dir, "diagnostico.json"), "w") as f:
            json.dump(diag, f, indent=2)
        return {"diagnostico": diag, "pf_messages": pf_messages, "timing": timing}

    # 5. Extraction
    step_start = time.time()
    
    buses_data = []
    for b in app.GetCalcRelevantObjects("*.ElmTerm"):
        buses_data.append({
            "loc_name": b.loc_name,
            "v_nom_kv": safe_get(b, "uknom", 0.0),
            "v_pu": safe_get(b, "m:u", 0.0),
            "v_kv": safe_get(b, "m:U", 0.0),
            "ang_deg": safe_get(b, "m:phiu", 0.0),
            "zona": get_zone(b)
        })
    with open(os.path.join(results_dir, "todas_las_barras.json"), "w") as f:
        json.dump(buses_data, f, indent=2)

    lines_data = []
    for l in app.GetCalcRelevantObjects("*.ElmLne"):
        if l.outserv == 1: continue
        lines_data.append({
            "loc_name": l.loc_name,
            "loading_pct": safe_get(l, "c:loading", 0.0),
            "p_mw": safe_get(l, "m:P:bus1", 0.0),
            "q_mvar": safe_get(l, "m:Q:bus1", 0.0),
            "bus1_name": l.bus1.cterm.loc_name if l.bus1 and l.bus1.cterm else "None",
            "bus2_name": l.bus2.cterm.loc_name if l.bus2 and l.bus2.cterm else "None",
            "zona": get_zone(l)
        })
    with open(os.path.join(results_dir, "todas_las_lineas.json"), "w") as f:
        json.dump(lines_data, f, indent=2)

    gens_data = []
    for g in app.GetCalcRelevantObjects("*.ElmSym"):
        if g.outserv == 1: continue
        gens_data.append({
            "loc_name": g.loc_name,
            "pgini": safe_get(g, "pgini", 0.0),
            "qgini": safe_get(g, "qgini", 0.0),
            "tipo": get_tech(g.loc_name),
            "zona": get_zone(g),
            "clase": "ElmSym"
        })
    for g in app.GetCalcRelevantObjects("*.ElmGenstat"):
        if g.outserv == 1: continue
        gens_data.append({
            "loc_name": g.loc_name,
            "pgini": safe_get(g, "pini", 0.0) or safe_get(g, "pgini", 0.0),
            "qgini": safe_get(g, "qini", 0.0) or safe_get(g, "qgini", 0.0),
            "tipo": get_tech(g.loc_name),
            "zona": get_zone(g),
            "clase": "ElmGenstat"
        })
    with open(os.path.join(results_dir, "todos_los_generadores.json"), "w") as f:
        json.dump(gens_data, f, indent=2)

    timing["extract_results_seconds"] = time.time() - step_start
    
    summary = {
        "status": "converged",
        "counts": {
            "buses": len(buses_data),
            "lines": len(lines_data),
            "generators": len(gens_data)
        },
        "totals": {
            "generation_mw": sum(g["pgini"] for g in gens_data),
            "generation_mvar": sum(g["qgini"] for g in gens_data)
        },
        "pf_messages": pf_messages,
        "timing": timing
    }
    return summary

if __name__ == "__main__":
    res = run_task()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    with open(os.path.join(results_dir, "summary.json"), "w") as f:
        json.dump(res, f, indent=2)
```
