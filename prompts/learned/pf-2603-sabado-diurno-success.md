# Flujo de Potencia 'Sabado Diurno' en Proyecto 2603 con Slack Distribuido

Fecha: 2026-04-07
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: 1. Activa el Study Case 'Base SEN' y el Escenario 'Sabado Diurno'. 2. Deshabilita ElmDsl. 3. Configura ComLdf (iopt_pbal=4, iopt_init=1, iopt_errlf=1). 4. Ejecuta flujo. 5. Obtén generación por tecnología (TER+GEO, HE+HP, PFV+CSP, PE, BESS). 6. Carga y pérdidas. Comparación con 8301 MW."

## Lecciones aprendidas
- **Consistencia de Escenarios**: Al igual que en el caso 'Laboral Vespertino', el uso de slack distribuido (`iopt_pbal=4`) permite la convergencia en bases de operación complejas.
- **Clasificación por Prefijo**: La lógica de clasificación basada en prefijos (`TER`, `GEO`, `HE`, `HP`, `PFV`, `CSP`, `PE`, `BESS`) es efectiva para el sistema chileno (CEN), donde los nombres de los elementos siguen una nomenclatura estandarizada.
- **Manejo de Errores DSL**: Deshabilitar todos los objetos `ElmDsl` (`outserv=1`) y configurar `iopt_errlf=1` en el comando de flujo es esencial para evitar fallos por DLLs faltantes en entornos de simulación que solo requieren cálculos estáticos.

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
    return "Otros"

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
    
    # Check cache
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
            return {"error": f"Import failed, no new project detected for {pfd_filename}"}

    proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # 2. Activate Study Case and Scenario
    step_start = time.time()
    all_cases = proj.GetContents("*.IntCase", 1)
    study_case = next((c for c in all_cases if c.loc_name == "Base SEN"), None)
    if not study_case:
        # Fallback to current if active case is not named Base SEN
        active_case = app.GetActiveStudyCase()
        if active_case and active_case.loc_name == "Base SEN":
            study_case = active_case
        else:
            return {"error": "Study case 'Base SEN' not found"}
    else:
        study_case.Activate()
    
    all_scenarios = proj.GetContents("*.IntScenario", 1)
    scenario = next((s for s in all_scenarios if s.loc_name == "Sabado Diurno"), None)
    if not scenario:
        return {"error": "Scenario 'Sabado Diurno' not found"}
    scenario.Activate()
    timing["activate_case_scenario_seconds"] = time.time() - step_start
    
    # 3. Disable all ElmDsl models
    step_start = time.time()
    dsl_models = app.GetCalcRelevantObjects("*.ElmDsl")
    for dsl in dsl_models:
        dsl.outserv = 1
    timing["disable_dsl_seconds"] = time.time() - step_start
    
    # 4. Run power flow
    step_start = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    
    # Configuration from prompt
    if ldf.HasAttribute("iopt_pbal"):
        ldf.SetAttribute("iopt_pbal", 4)  # Slack distribuido por generadores síncronos
    if ldf.HasAttribute("iopt_init"):
        ldf.SetAttribute("iopt_init", 1)  # Flat start
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
        
    # Extract results
    step_start = time.time()
    
    tech_mw = {
        "Térmica": 0.0,
        "Hidráulica": 0.0,
        "Solar": 0.0,
        "Eólica": 0.0,
        "Almacenamiento": 0.0,
        "Otros": 0.0
    }
    
    # Generators
    all_gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_gens:
        if g.outserv == 0:
            tech = get_tech(g.loc_name)
            if tech == "Excluded":
                continue
            
            p = safe_get(g, "m:P:bus1", 0.0)
            if tech in tech_mw:
                tech_mw[tech] += p
    
    total_gen_mw = sum(tech_mw.values())
    
    # Loads
    all_loads = app.GetCalcRelevantObjects("*.ElmLod") + app.GetCalcRelevantObjects("*.ElmLode")
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

    # Calculate mix percentages (ignoring "Otros")
    mix = {}
    valid_techs = ["Térmica", "Hidráulica", "Solar", "Eólica", "Almacenamiento"]
    sum_valid_gen = sum(tech_mw[t] for t in valid_techs)
    
    if sum_valid_gen > 0:
        for t in valid_techs:
            mix[f"{t}%"] = (tech_mw[t] / sum_valid_gen) * 100.0
    else:
        for t in valid_techs:
            mix[f"{t}%"] = 0.0
            
    # Reference comparison
    ref_cen = 8301.0
    delta_mw = total_gen_mw - ref_cen
    delta_percent = (delta_mw / ref_cen) * 100.0 if ref_cen != 0 else 0.0
    
    timing["extract_results_seconds"] = time.time() - step_start
    
    # Remove "Otros" from technologies for final output
    tech_out = {t: tech_mw[t] for t in valid_techs}

    final_results = {
        "resumen": {
            "gen_total": total_gen_mw,
            "load_total": total_load_mw,
            "losses_total": losses_mw,
            "converged": (error_code == 0)
        },
        "tecnologias": tech_out,
        "mix": mix,
        "comparacion": {
            "referencia_cen_mw": ref_cen,
            "delta_mw": delta_mw,
            "delta_percent": delta_percent
        },
        "pf_messages": pf_messages,
        "timing": timing,
        "error_code": error_code
    }
    
    return final_results

if __name__ == "__main__":
    results = run_task()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    with open(os.path.join(results_dir, "power_flow.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
```
```
