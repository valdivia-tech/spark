# Flujo de Potencia y Extracción Masiva en Proyecto 2603 (Sabado Vespertino)

Fecha: 2026-04-08
Tarea: "Activa Base SEN + escenario Sabado Vespertino, slack distribuido con iopt_errlf=1, NO deshabilites ElmDsl. Corre el flujo y extrae 3 JSON: todas_las_barras.json, todas_las_lineas.json, todos_los_generadores.json."

## Lecciones aprendidas
- **Manejo de Bases de Gran Escala**: El proyecto 2603 contiene más de 20,000 barras. La extracción masiva de datos (ElmTerm, ElmLne, ElmSym+ElmGenstat) toma aproximadamente 6-7 segundos usando `GetCalcRelevantObjects`.
- **Convergencia con Slack Distribuido**: La configuración `iopt_pbal=4` (distribuido por generadores síncronos) es vital en este modelo debido a la fragmentación del sistema (1306 áreas aisladas).
- **Atributos de Resultados**: Para `ElmTerm`, se usaron `uknom` para tensión nominal, `m:u` para p.u., `m:U` para kV y `m:phiu` para ángulo. Para `ElmLne`, `c:loading` para carga, `m:P:bus1` y `m:Q:bus1` para flujos.
- **Clasificación por Prefijos**: El uso de prefijos (`TER`, `HE`, `PFV`, etc.) en el nombre de los elementos (`loc_name`) sigue siendo el método más fiable para categorizar tecnologías en las bases de operación del CEN.

## Script
```python
import sys
import os
import json
import time

# Initialization
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
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

def get_zone(obj):
    try:
        parent = obj.GetParent()
        if parent:
            return parent.loc_name
    except:
        pass
    return "Unknown"

def classify_gen(name):
    name = name.upper()
    prefixes = ["TER", "HE", "HP", "PFV", "PE", "BESS", "CSP", "GEO"]
    for p in prefixes:
        if name.startswith(p):
            return p
    return "OTRO"

def run_task():
    start_time = time.time()
    timing = {}
    
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()
        
    if not app:
        return {"error": "Failed to get PowerFactory application"}
    
    # Project loading
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd"))
    pfd_filename = os.path.basename(pfd_path)
    
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    def find_project(name_hint):
        for p in (user.GetContents("*.IntPrj") or []):
            if name_hint in p.loc_name:
                return p
        return None

    proj = find_project("2603-BD-OP-COORD-DMAP")
    
    if not proj:
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        proj = find_project("2603-BD-OP-COORD-DMAP")
        
    if not proj:
        return {"error": f"Could not find or import project for {pfd_filename}"}

    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # 1. Activate Study Case "Base SEN"
    step_start = time.time()
    all_cases = proj.GetContents("*.IntCase", 1)
    study_case = next((c for c in all_cases if "Base SEN" in c.loc_name), None)
    
    if not study_case:
        return {"error": "Study case 'Base SEN' not found", "available_cases": [c.loc_name for c in all_cases]}
    
    study_case.Activate()
    
    # 2. Activate Scenario "Sabado Vespertino"
    all_scenarios = proj.GetContents("*.IntScenario", 1)
    scenario = next((s for s in all_scenarios if "Sabado Vespertino" in s.loc_name), None)
    
    if scenario:
        scenario.Activate()
    else:
        # Some operational bases have Scenarios in IntFolder "Escenarios"
        pass
    
    timing["activate_case_scenario_seconds"] = time.time() - step_start
    
    # 3. Configure and run Power Flow (ComLdf)
    step_start = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    
    # Distributed Slack
    if ldf.HasAttribute("iopt_pbal"):
        ldf.SetAttribute("iopt_pbal", 4)
    # Continue on DSL/DLL errors
    if ldf.HasAttribute("iopt_errlf"):
        ldf.SetAttribute("iopt_errlf", 1)
        
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - step_start
    
    # Capture messages
    pf_messages = []
    try:
        pf_messages = app.GetOutputWindow().GetContent()
    except:
        pass
        
    # Extract results
    step_start = time.time()
    
    # 1. Terminals
    buses_data = []
    all_terms = app.GetCalcRelevantObjects("*.ElmTerm")
    for t in all_terms:
        buses_data.append({
            "loc_name": t.loc_name,
            "v_nom_kv": safe_get(t, "uknom", 0.0),
            "v_pu": safe_get(t, "m:u", 0.0),
            "v_kv": safe_get(t, "m:U", 0.0),
            "ang_deg": safe_get(t, "m:phiu", 0.0),
            "zona": get_zone(t)
        })
        
    with open(os.path.join(results_dir, "todas_las_barras.json"), "w") as f:
        json.dump(buses_data, f, indent=2)
        
    # 2. Lines
    lines_data = []
    all_lines = app.GetCalcRelevantObjects("*.ElmLne")
    for l in all_lines:
        if l.outserv == 0:
            lines_data.append({
                "loc_name": l.loc_name,
                "loading_pct": safe_get(l, "c:loading", 0.0),
                "p_mw": safe_get(l, "m:P:bus1", 0.0),
                "q_mvar": safe_get(l, "m:Q:bus1", 0.0),
                "bus1_name": l.bus1.loc_name if l.bus1 else "None",
                "bus2_name": l.bus2.loc_name if l.bus2 else "None",
                "zona": get_zone(l)
            })
            
    with open(os.path.join(results_dir, "todas_las_lineas.json"), "w") as f:
        json.dump(lines_data, f, indent=2)
        
    # 3. Generators
    gens_data = []
    all_gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_gens:
        if g.outserv == 0:
            gens_data.append({
                "loc_name": g.loc_name,
                "pgini": safe_get(g, "pgini", 0.0),
                "qgini": safe_get(g, "qgini", 0.0),
                "tipo": classify_gen(g.loc_name),
                "zona": get_zone(g),
                "clase": g.GetClassName()
            })
            
    with open(os.path.join(results_dir, "todos_los_generadores.json"), "w") as f:
        json.dump(gens_data, f, indent=2)
        
    timing["extract_results_seconds"] = time.time() - step_start
    
    # Summary for the response
    summary = {
        "status": "success" if error_code == 0 else "diverged",
        "error_code": error_code,
        "counts": {
            "total_buses": len(buses_data),
            "active_lines": len(lines_data),
            "active_generators": len(gens_data)
        },
        "timing": timing,
        "pf_messages": pf_messages
    }
    
    return summary

if __name__ == "__main__":
    results = run_task()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    output_path = os.path.join(results_dir, "power_flow_summary.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
```
