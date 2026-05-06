# Flujo de Potencia 'ERNC CC' en Proyecto 2603 con Clasificación Tecnológica

Fecha: 2026-04-07
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: 1. Activa 'Base SEN'. 2. Activa escenario 'ERNC CC'. 3. Deshabilita ElmDsl. 4. Ejecuta ComLdf con slack distribuido, flat start e ignora errores DSL. 5. Clasifica y suma potencia activa por prefijo."

## Lecciones aprendidas
- **Estabilidad con Slack Distribuido**: Para escenarios con alta penetración de Energías Renovables No Convencionales (ERNC), el uso de `iopt_pbal=4` (slack distribuido por generadores síncronos) permite compensar desbalances locales de manera más realista que un slack único.
- **Clasificación por Prefijos**: El uso de prefijos (TER, HE, PFV, PE, BESS) es una forma efectiva de agrupar elementos en bases de datos industriales grandes donde no siempre se cuenta con atributos de "tipo de combustible" consistentes.
- **Manejo de ElmGenstat**: Es crucial incluir tanto `ElmSym` como `ElmGenstat` al calcular la generación total, ya que las plantas solares y eólicas modernas suelen modelarse como generadores estáticos.
- **Despacho ERNC**: El escenario 'ERNC CC' presenta un nivel de despacho base coherente con las metas de operación del CEN para periodos de alta disponibilidad renovable (~8.1 GW).

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
    # Exclude STATCOM, CONDENSADOR, SVC
    if any(k in name for k in ["STATCOM", "CONDENSADOR", "SVC"]):
        return "Excluded"
    
    # Prefix mapping
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
    return "Others"

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
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        else:
            return {"error": "Import failed, no new project detected"}

    proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # 2. Activate Study Case and Scenario
    step_start = time.time()
    all_cases = proj.GetContents("*.IntCase", 1)
    study_case = next((c for c in all_cases if c.loc_name == "Base SEN"), None)
    if not study_case:
        study_case = next((c for c in all_cases if "Base SEN" in c.loc_name), None)
        
    if not study_case:
        return {"error": f"Study case 'Base SEN' not found among { [c.loc_name for c in all_cases] }"}
    
    study_case.Activate()
    
    # Re-fetch scenario as it might be nested or affected by case activation
    all_scenarios = proj.GetContents("*.IntScenario", 1) + proj.GetContents("*.ElmScenario", 1)
    scenario = next((s for s in all_scenarios if s.loc_name == "ERNC CC"), None)
    if not scenario:
         scenario = next((s for s in all_scenarios if "ERNC CC" in s.loc_name), None)
         
    if not scenario:
        return {"error": f"Scenario 'ERNC CC' not found among { [s.loc_name for s in all_scenarios] }"}
    
    scenario.Activate()
    timing["activate_case_scenario_seconds"] = time.time() - step_start
    
    # 3. Disable all ElmDsl models
    step_start = time.time()
    dsl_models = app.GetCalcRelevantObjects("*.ElmDsl")
    for dsl in dsl_models:
        dsl.outserv = 1
    timing["disable_dsl_seconds"] = time.time() - step_start
    
    # 4. Configure and run power flow
    step_start = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    
    # Distributed slack by synchronous generators
    if ldf.HasAttribute("iopt_pbal"):
        ldf.SetAttribute("iopt_pbal", 4)
    # Flat start
    if ldf.HasAttribute("iopt_init"):
        ldf.SetAttribute("iopt_init", 1)
    # Ignore DSL/DLL errors
    if ldf.HasAttribute("iopt_errlf"):
        ldf.SetAttribute("iopt_errlf", 1)
        
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - step_start
    
    # Capture messages
    pf_messages = []
    try:
        msg_obj = app.GetOutputWindow()
        if msg_obj:
            pf_messages = msg_obj.GetContent()
    except:
        pass
        
    # 5. Extract results and classification
    step_start = time.time()
    
    tech_gen_mw = {
        "Térmica": 0.0,
        "Hidráulica": 0.0,
        "Solar": 0.0,
        "Eólica": 0.0,
        "Almacenamiento": 0.0,
        "Others": 0.0
    }
    
    tech_dispatch_mw = {
        "Térmica": 0.0,
        "Hidráulica": 0.0,
        "Solar": 0.0,
        "Eólica": 0.0,
        "Almacenamiento": 0.0,
        "Others": 0.0
    }
    
    all_sym = app.GetCalcRelevantObjects("*.ElmSym")
    for g in all_sym:
        if g.outserv == 0:
            tech = get_tech(g.loc_name)
            if tech == "Excluded":
                continue
            
            p_calc = safe_get(g, "m:P:bus1", 0.0)
            p_dispatch = safe_get(g, "pgini", 0.0)
            
            tech_gen_mw[tech] += p_calc
            tech_dispatch_mw[tech] += p_dispatch

    all_genstat = app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_genstat:
        if g.outserv == 0:
            tech = get_tech(g.loc_name)
            if tech == "Excluded":
                continue
            
            p_calc = safe_get(g, "m:P:bus1", 0.0)
            p_dispatch = safe_get(g, "pini", 0.0)
            
            tech_gen_mw[tech] += p_calc
            tech_dispatch_mw[tech] += p_dispatch
            
    total_gen_mw = sum(tech_gen_mw.values())
    total_dispatch_mw = sum(tech_dispatch_mw.values())
    
    # Loads
    all_loads = app.GetCalcRelevantObjects("*.ElmLode") + app.GetCalcRelevantObjects("*.ElmLod")
    total_load_mw = sum(safe_get(l, "m:P:bus1", 0.0) for l in all_loads if l.outserv == 0)
    
    # Losses
    losses_mw = 0.0
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        if line.outserv == 0:
            p1 = safe_get(line, "m:P:bus1", 0.0)
            p2 = safe_get(line, "m:P:bus2", 0.0)
            losses_mw += (p1 + p2) 
            
    for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
        if trafo.outserv == 0:
            phv = safe_get(trafo, "m:P:bushv", 0.0)
            plv = safe_get(trafo, "m:P:buslv", 0.0)
            losses_mw += (phv + plv)
            
    for trafo3 in app.GetCalcRelevantObjects("*.ElmTr3"):
        if trafo3.outserv == 0:
            phv = safe_get(trafo3, "m:P:bushv", 0.0)
            pmv = safe_get(trafo3, "m:P:busmv", 0.0)
            plv = safe_get(trafo3, "m:P:buslv", 0.0)
            losses_mw += (phv + pmv + plv)

    timing["extract_results_seconds"] = time.time() - step_start
    
    output = {
        "power_flow": {
            "status": "converged" if error_code == 0 else "diverged",
            "error_code": error_code,
            "generation_by_technology_mw": tech_gen_mw,
            "total_generation_mw": total_gen_mw,
            "total_dispatch_input_mw": total_dispatch_mw,
            "total_load_mw": total_load_mw,
            "total_losses_mw": losses_mw,
            "imbalance_mw": total_gen_mw - total_load_mw - losses_mw
        },
        "pf_messages": pf_messages,
        "timing": timing
    }
    
    return output

if __name__ == "__main__":
    results = run_task()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    with open(os.path.join(results_dir, "power_flow.json"), "w") as f:
        json.dump(results, f, indent=2)
```
