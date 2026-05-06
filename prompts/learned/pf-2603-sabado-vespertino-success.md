# Flujo de Potencia 'Sabado Vespertino' en Proyecto 2603 (Inercia y DSL activos)

Fecha: 2026-04-07
Tarea: "En el proyecto '2603-BD-OP-COORD-DMAP.pfd': 1. Activar 'Base SEN'. 2. Activar 'Sabado Vespertino'. 3. Configurar ComLdf: iopt_pbal=4, iopt_errlf=1, iopt_init=1. 4. Correr flujo. 5. Si falla, usar iopt_init=0. 6. Recopilar resultados globales y por categoría técnica (TER/GEO, HE/HP, PFV/CSP, PE, BESS)."

## Lecciones aprendidas
- **Convergencia con Modelos DSL**: A diferencia de casos anteriores donde se solicitaba deshabilitar `ElmDsl`, este caso se ejecutó con todos los modelos dinámicos activos. La configuración `iopt_errlf=1` permitió ignorar errores de carga de DLLs (comunes en bases de operación chilenas) y converger exitosamente en 6 iteraciones.
- **Robustez de Slack Distribuido**: El uso de `iopt_pbal=4` (Slack distribuido por generadores síncronos) es fundamental en este sistema fragmentado (1306 áreas aisladas detectadas). El balance se cierra con un ajuste de -77.9 MW distribuido entre las unidades de control.
- **Consistencia de Escenario 'Vespertino'**: Se observa una generación solar de 220 MW (baja, consistente con el atardecer) y una descarga significativa de almacenamiento (BESS) de 711 MW, típica para cubrir la rampa de demanda vespertina en el SEN.
- **Manejo de Importación**: En entornos multi-tarea, es más robusto buscar el proyecto por nombre (`2603-BD-OP-COORD-DMAP`) antes de intentar una importación que podría fallar si el archivo ya fue cargado por otro proceso o en una ejecución previa sin limpiar el caché.

## Script
```python
import sys
import os
import json
import time

# PowerFactory initialization
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

def classify_gen(name):
    name = name.upper()
    if any(name.startswith(p) for p in ["TER", "GEO"]):
        return "Térmica"
    if any(name.startswith(p) for p in ["HE", "HP"]):
        return "Hidráulica"
    if any(name.startswith(p) for p in ["PFV", "CSP"]):
        return "Solar"
    if name.startswith("PE"):
        return "Eólica"
    if name.startswith("BESS"):
        return "Almacenamiento"
    return "Otros"

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
    
    # Improved project lookup
    def find_project(name_hint):
        for p in (user.GetContents("*.IntPrj") or []):
            if name_hint in p.loc_name:
                return p
        return None

    # Try to find existing first
    proj = find_project("2603-BD-OP-COORD-DMAP")
    
    if not proj:
        # Import
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        
        # Look again
        proj = find_project("2603-BD-OP-COORD-DMAP")
        
    if not proj:
        return {"error": f"Could not find or import project for {pfd_filename}"}

    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # 1. Activate Study Case "Base SEN"
    step_start = time.time()
    all_cases = proj.GetContents("*.IntCase", 1)
    study_case = next((c for c in all_cases if c.loc_name == "Base SEN"), None)
    if not study_case:
        # Try search by name partial
        study_case = next((c for c in all_cases if "Base SEN" in c.loc_name), None)
        
    if not study_case:
        return {"error": "Study case 'Base SEN' not found", "available_cases": [c.loc_name for c in all_cases]}
    
    study_case.Activate()
    
    # 2. Activate Scenario "Sabado Vespertino"
    all_scenarios = proj.GetContents("*.IntScenario", 1)
    scenario = next((s for s in all_scenarios if s.loc_name == "Sabado Vespertino"), None)
    if not scenario:
         scenario = next((s for s in all_scenarios if "Sabado Vespertino" in s.loc_name), None)
         
    if not scenario:
        return {"error": "Scenario 'Sabado Vespertino' not found", "available_scenarios": [s.loc_name for s in all_scenarios]}
        
    scenario.Activate()
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
    # Flat start
    if ldf.HasAttribute("iopt_init"):
        ldf.SetAttribute("iopt_init", 1)
        
    error_code = ldf.Execute()
    
    # If it fails, try Snapshot start
    if error_code != 0:
        if ldf.HasAttribute("iopt_init"):
            ldf.SetAttribute("iopt_init", 0) # Snapshot start
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
    
    categories = {
        "Térmica": {"mw": 0.0, "count": 0},
        "Hidráulica": {"mw": 0.0, "count": 0},
        "Solar": {"mw": 0.0, "count": 0},
        "Eólica": {"mw": 0.0, "count": 0},
        "Almacenamiento": {"mw": 0.0, "count": 0},
        "Otros": {"mw": 0.0, "count": 0}
    }
    
    all_gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_gens:
        if g.outserv == 0:
            cat = classify_gen(g.loc_name)
            p = safe_get(g, "m:P:bus1", 0.0)
            categories[cat]["mw"] += p
            categories[cat]["count"] += 1
            
    total_gen_mw = sum(c["mw"] for c in categories.values())
    
    # Global: Total Load
    all_loads = app.GetCalcRelevantObjects("*.ElmLode") + app.GetCalcRelevantObjects("*.ElmLod")
    total_load_mw = sum(safe_get(l, "m:P:bus1", 0.0) for l in all_loads if l.outserv == 0)
    
    # Global: Total Losses
    total_losses_mw = 0.0
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        if line.outserv == 0:
            p1 = safe_get(line, "m:P:bus1", 0.0)
            p2 = safe_get(line, "m:P:bus2", 0.0)
            total_losses_mw += (p1 + p2) 
            
    for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
        if trafo.outserv == 0:
            phv = safe_get(trafo, "m:P:bushv", 0.0)
            plv = safe_get(trafo, "m:P:buslv", 0.0)
            total_losses_mw += (phv + plv)
            
    for trafo3 in app.GetCalcRelevantObjects("*.ElmTr3"):
        if trafo3.outserv == 0:
            phv = safe_get(trafo3, "m:P:bushv", 0.0)
            pmv = safe_get(trafo3, "m:P:busmv", 0.0)
            plv = safe_get(trafo3, "m:P:buslv", 0.0)
            total_losses_mw += (phv + pmv + plv)

    timing["extract_results_seconds"] = time.time() - step_start
    
    output = {
        "status": "success" if error_code == 0 else "diverged",
        "error_code": error_code,
        "global_results": {
            "total_generation_mw": total_gen_mw,
            "total_load_mw": total_load_mw,
            "total_losses_mw": total_losses_mw,
            "imbalance_mw": total_gen_mw - total_load_mw - total_losses_mw
        },
        "generation_by_category": categories,
        "pf_messages": pf_messages,
        "timing": timing
    }
    
    return output

if __name__ == "__main__":
    results = run_task()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    output_path = os.path.join(results_dir, "power_flow_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
```
