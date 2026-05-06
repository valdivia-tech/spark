# Extracción masiva de datos en 2603-BD-OP-COORD-DMAP (Sabado Diurno)

Fecha: 2026-04-08
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: Activa Base SEN + escenario Sabado Diurno, slack distribuido con iopt_errlf=1, NO deshabilites ElmDsl. Corre el flujo y extrae 3 JSON: 1) todas_las_barras.json, 2) todas_las_lineas.json, 3) todos_los_generadores.json."

## Lecciones aprendidas
- **Acceso a Zona**: El atributo `cpParent` puede no estar disponible directamente como atributo en el objeto de datos; usar `GetParent().loc_name` es más robusto para obtener la carpeta contenedora (Zona).
- **Importación y Cache**: Si un proyecto ya existe en el entorno, el objeto `CompfdImport` no detectará un "nuevo" proyecto. Es vital buscar por nombre esperado o prefijo (ej: "2603") antes de fallar.
- **Escalabilidad**: El sistema maneja >20,000 barras y >3,000 líneas sin problemas de memoria en la extracción a JSON.
- **Configuración de Flujo**: Mantener `ElmDsl` activo mientras se usa `iopt_errlf=1` permite que el flujo corra incluso si faltan DLLs de modelos dinámicos, lo cual es común en bases de operación del CEN.

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

def get_zone(obj):
    try:
        parent = obj.GetParent()
        if parent and parent.loc_name:
            return parent.loc_name
    except:
        pass
    return "N/A"

def classify_gen(name):
    name = name.upper()
    prefixes = ["TER", "HE", "HP", "PFV", "PE", "BESS", "CSP", "GEO"]
    for p in prefixes:
        if name.startswith(p):
            return p
    return "OTROS"

def run_task():
    start_time = time.time()
    timing = {}
    
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)
        
    if not app:
        return {"error": "Failed to get PowerFactory application"}
    
    # 1. Project loading
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd"))
    pfd_filename = os.path.basename(pfd_path)
    
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    cache_file = os.path.join(results_dir, ".project_cache.json")
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cache = json.load(f)
            
    project_name = cache.get(pfd_filename)
    all_projects = user.GetContents("*.IntPrj") or []

    if project_name:
        if not any(p.loc_name == project_name for p in all_projects):
            project_name = None

    if not project_name:
        # Check if it already exists by typical name
        expected_name = "2603-BD-OP-COORD-DMAP"
        proj = next((p for p in all_projects if p.loc_name == expected_name), None)
        if proj:
            project_name = expected_name
        else:
            projects_before = {p.loc_name for p in all_projects}
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
                proj = next((p for p in user.GetContents("*.IntPrj") if "2603" in p.loc_name), None)
                if proj:
                    project_name = proj.loc_name
                else:
                    return {"error": f"Import failed, no project detected for {pfd_filename}"}

        # Save to cache
        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)

    proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # 2. Activate Study Case and Scenario
    step_start = time.time()
    all_cases = proj.GetContents("*.IntCase", 1)
    study_case = next((c for c in all_cases if "Base SEN" in c.loc_name), None)
    if not study_case:
        if all_cases:
            study_case = all_cases[0]
        else:
            return {"error": "No study case found"}
    study_case.Activate()
    
    all_scenarios = proj.GetContents("*.IntScenario", 1)
    scenario = next((s for s in all_scenarios if "Sabado Diurno" in s.loc_name), None)
    if not scenario:
        return {"error": "Scenario 'Sabado Diurno' not found"}
    scenario.Activate()
    timing["activate_case_scenario_seconds"] = time.time() - step_start
    
    # 3. Run power flow
    step_start = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    
    if ldf.HasAttribute("iopt_pbal"):
        ldf.SetAttribute("iopt_pbal", 4)  # Slack distribuido
    if ldf.HasAttribute("iopt_errlf"):
        ldf.SetAttribute("iopt_errlf", 1) # Ignorar errores DSL
        
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - step_start
    
    # Capture messages
    pf_messages = []
    try:
        ow = app.GetOutputWindow()
        pf_messages = ow.GetContent()
    except:
        pass
        
    if error_code != 0:
        gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
        loads = app.GetCalcRelevantObjects("*.ElmLod") + app.GetCalcRelevantObjects("*.ElmLode")
        diag = {
            "status": "diverged",
            "error_code": error_code,
            "project": project_name,
            "study_case": study_case.loc_name,
            "diagnosis": {
                "total_generation_mw": sum(safe_get(g, "m:P:bus1", 0.0) for g in gens if g.outserv == 0),
                "total_load_mw": sum(safe_get(l, "m:P:bus1", 0.0) for l in loads if l.outserv == 0),
                "slack_bus_found": len(app.GetCalcRelevantObjects("*.ElmXnet")) > 0,
                "external_grid_active": any(x.outserv == 0 for x in app.GetCalcRelevantObjects("*.ElmXnet")),
                "isolated_buses": len([b for b in app.GetCalcRelevantObjects("*.ElmTerm") if safe_get(b, "m:u", 0) == 0])
            },
            "recommendations": ["Check slack distribution", "Verify scenario activation"]
        }
        with open(os.path.join(results_dir, "diagnostico.json"), "w") as f:
            json.dump(diag, f, indent=2)
        return diag

    # 4. Extract results
    step_start = time.time()
    
    barras_list = []
    for b in app.GetCalcRelevantObjects("*.ElmTerm"):
        barras_list.append({
            "loc_name": b.loc_name,
            "v_nom_kv": safe_get(b, "uknom", 0.0),
            "v_pu": safe_get(b, "m:u", 0.0),
            "v_kv": safe_get(b, "m:U", 0.0),
            "ang_deg": safe_get(b, "m:phiu", 0.0),
            "zona": get_zone(b)
        })
    with open(os.path.join(results_dir, "todas_las_barras.json"), "w") as f:
        json.dump(barras_list, f, indent=2)

    lineas_list = []
    for l in app.GetCalcRelevantObjects("*.ElmLne"):
        if l.outserv == 0:
            bus1 = l.bus1.GetParent() if l.bus1 else None
            bus2 = l.bus2.GetParent() if l.bus2 else None
            lineas_list.append({
                "loc_name": l.loc_name,
                "loading_pct": safe_get(l, "c:loading", 0.0),
                "p_mw": safe_get(l, "m:P:bus1", 0.0),
                "q_mvar": safe_get(l, "m:Q:bus1", 0.0),
                "bus1_name": bus1.loc_name if bus1 else "N/A",
                "bus2_name": bus2.loc_name if bus2 else "N/A",
                "zona": get_zone(l)
            })
    with open(os.path.join(results_dir, "todas_las_lineas.json"), "w") as f:
        json.dump(lineas_list, f, indent=2)

    gens_list = []
    all_gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_gens:
        if g.outserv == 0:
            gens_list.append({
                "loc_name": g.loc_name,
                "pgini": safe_get(g, "pgini", 0.0),
                "qgini": safe_get(g, "qgini", 0.0),
                "p_mw": safe_get(g, "m:P:bus1", 0.0),
                "q_mvar": safe_get(g, "m:Q:bus1", 0.0),
                "tipo": classify_gen(g.loc_name),
                "zona": get_zone(g),
                "clase": g.GetClassName()
            })
    with open(os.path.join(results_dir, "todos_los_generadores.json"), "w") as f:
        json.dump(gens_list, f, indent=2)

    timing["extract_results_seconds"] = time.time() - step_start
    
    resumen = {
        "status": "success",
        "barras_count": len(barras_list),
        "lineas_count": len(lineas_list),
        "generadores_count": len(gens_list),
        "total_gen_mw": sum(g["p_mw"] for g in gens_list),
        "total_load_mw": sum(safe_get(l, "m:P:bus1", 0.0) for l in app.GetCalcRelevantObjects("*.ElmLod") if l.outserv == 0),
        "timing": timing,
        "pf_messages": pf_messages
    }
    
    with open(os.path.join(results_dir, "resumen.json"), "w") as f:
        json.dump(resumen, f, indent=2)
        
    return resumen

if __name__ == "__main__":
    results = run_task()
    print(json.dumps(results, indent=2))
```
