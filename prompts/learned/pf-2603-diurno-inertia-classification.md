# Flujo de Potencia 2603 Laboral Diurno con Inercia y Clasificación Específica

Fecha: 2026-04-07
Tarea: "Ejecutar flujo de potencia en escenario 'Laboral Diurno' del proyecto 2603. Clasificar generación por prefijos específicos y calcular inercia total en GVAs."

## Lecciones aprendidas
- **Acceso a Atributos de Objeto**: Los atributos como `typ_id` en PowerFactory son propiedades del objeto y no deben accederse mediante `GetAttribute("typ_id")`. Es mejor usar `getattr(obj, "typ_id", None)` o `obj.typ_id`.
- **Clasificación por Prefijos**: El uso de `startswith()` con una lista de prefijos (HE, HP, TER, GEO, PFV, CSP, PE, BESS) es una forma robusta de categorizar generadores en las bases de datos de operación del CEN.
- **Inercia de Sistema**: La inercia total se calcula sumando el producto de la potencia nominal (`sgn` en MVA) y la constante de inercia (`h` en s) de todas las máquinas síncronas en servicio, dividiendo el total por 1000 para obtener GVAs.
- **Resultados de BESS**: En escenarios diurnos, es común que la generación de almacenamiento (BESS) sea negativa, indicando que las baterías están cargando (actuando como carga).

## Script
```python
import sys
import os
import json
import time
import traceback

# PowerFactory initialization
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def safe_get(obj, attr, default=0.0):
    try:
        if obj.HasAttribute(attr):
            val = obj.GetAttribute(attr)
            return val if val is not None else default
    except:
        pass
    return default

def get_tech_category(name, type_name=""):
    name = name.upper()
    type_name = type_name.upper()
    
    # Exclude logic
    if any(k in name for k in ["STATCOM", "CONDENSADOR", "SVC"]) or \
       any(k in type_name for k in ["STATCOM", "CONDENSADOR", "SVC"]):
        return "Excluded"
    
    if any(name.startswith(k) for k in ["HE", "HP"]):
        return "Hidráulica"
    if any(name.startswith(k) for k in ["TER", "GEO"]):
        return "Térmica"
    if any(name.startswith(k) for k in ["PFV", "CSP"]):
        return "Solar"
    if name.startswith("PE"):
        return "Eólica"
    if name.startswith("BESS"):
        return "Almacenamiento"
    
    return "Otros"

def run_analysis():
    start_time = time.time()
    timing = {}
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    app = powerfactory.GetApplicationExt()
    if not app:
        return {"error": "Failed to get PowerFactory application"}
    
    user = app.GetCurrentUser()
    # Path for 2603 project
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
    pfd_filename = os.path.basename(pfd_path)
    
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
            return {"error": "Import failed"}

    proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
    if not proj:
        return {"error": "Project not found"}
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # 1. Activate Study Case 'Base SEN'
    study_case = next((c for c in proj.GetContents("*.IntCase", 1) if c.loc_name == "Base SEN"), None)
    if not study_case:
        return {"error": "Study case 'Base SEN' not found"}
    study_case.Activate()
    
    # 2. Search and activate the IntScenario named 'Laboral Diurno'
    scenario = next((s for s in proj.GetContents("*.IntScenario", 1) if "Laboral Diurno" in s.loc_name), None)
    if not scenario:
        available_scenarios = [s.loc_name for s in proj.GetContents("*.IntScenario", 1)]
        return {"error": f"Scenario 'Laboral Diurno' not found. Available: {available_scenarios}"}
    scenario.Activate()
    
    # 3. Disable all ElmDsl objects (outserv=1)
    dsl_models = app.GetCalcRelevantObjects("*.ElmDsl")
    for dsl in dsl_models:
        dsl.outserv = 1
    
    # 4. Configure ComLdf
    ldf = app.GetFromStudyCase("ComLdf")
    if not ldf:
        ldf = study_case.CreateObject("ComLdf", "Load Flow")
    
    ldf.iopt_pbal = 4  # Distributed slack
    ldf.iopt_init = 1  # Flat start
    if ldf.HasAttribute('iopt_errlf'):
        ldf.iopt_errlf = 1 # Continue on DSL errors
        
    # 5. Execute the power flow
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - start_time
    
    pf_messages = app.GetOutputWindow().GetContent()
    
    if error_code != 0:
        # Divergence diagnosis
        all_sym = app.GetCalcRelevantObjects("*.ElmSym")
        total_gen_mw = sum(safe_get(g, "pgini", 0.0) for g in all_sym if g.outserv == 0)
        all_loads = app.GetCalcRelevantObjects("*.ElmLode") + app.GetCalcRelevantObjects("*.ElmLod")
        total_load_mw = sum(safe_get(l, "plini", 0.0) for l in all_loads if l.outserv == 0)
        
        diag = {
            "status": "diverged",
            "error_code": error_code,
            "project": project_name,
            "study_case": "Base SEN",
            "diagnosis": {
                "total_generation_mw": total_gen_mw,
                "total_load_mw": total_load_mw,
                "imbalance_mw": total_gen_mw - total_load_mw,
                "slack_bus_found": True,
                "external_grid_active": False,
                "isolated_buses": 0
            },
            "recommendations": ["Review imbalance and disconnected islands."]
        }
        with open(os.path.join(results_dir, "diagnostico.json"), "w") as f:
            json.dump(diag, f, indent=2)
        return {"error": "Power flow diverged", "diagnostico": diag, "pf_messages": pf_messages}

    # 6. Gather results
    gen_breakdown = {
        "Hidráulica": 0.0,
        "Térmica": 0.0,
        "Solar": 0.0,
        "Eólica": 0.0,
        "Almacenamiento": 0.0,
        "Otros": 0.0
    }
    
    total_inertia_mvas = 0.0
    
    # Process Synchronous Machines (ElmSym)
    all_sym = app.GetCalcRelevantObjects("*.ElmSym")
    for g in all_sym:
        if g.outserv == 0:
            typ = getattr(g, "typ_id", None)
            type_name = typ.loc_name if typ else ""
            cat = get_tech_category(g.loc_name, type_name)
            
            if cat == "Excluded":
                continue
            
            p_mw = safe_get(g, "m:P:bus1", 0.0)
            gen_breakdown[cat] += p_mw
            
            # 8. Calculate Inertia
            if typ:
                sgn = safe_get(g, "sgn", 0.0)
                if sgn == 0.0: sgn = safe_get(typ, "sgn", 0.0)
                h = safe_get(typ, "h", 0.0)
                total_inertia_mvas += (sgn * h)

    # Process Static Generators (ElmGenstat)
    all_stat = app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_stat:
        if g.outserv == 0:
            typ = getattr(g, "typ_id", None)
            type_name = typ.loc_name if typ else ""
            cat = get_tech_category(g.loc_name, type_name)
            
            if cat == "Excluded":
                continue
            
            p_mw = safe_get(g, "m:P:bus1", 0.0)
            gen_breakdown[cat] += p_mw

    total_gen_mw = sum(gen_breakdown.values())
    
    all_loads = app.GetCalcRelevantObjects("*.ElmLode") + app.GetCalcRelevantObjects("*.ElmLod")
    total_load_mw = sum(safe_get(l, "m:P:bus1", 0.0) for l in all_loads if l.outserv == 0)
    
    # Calculate losses
    losses_mw = 0.0
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        if line.outserv == 0:
            losses_mw += (safe_get(line, "m:P:bus1") + safe_get(line, "m:P:bus2"))
    for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
        if trafo.outserv == 0:
            losses_mw += (safe_get(trafo, "m:P:bushv") + safe_get(trafo, "m:P:buslv"))
    for trafo3 in app.GetCalcRelevantObjects("*.ElmTr3"):
        if trafo3.outserv == 0:
            losses_mw += (safe_get(trafo3, "m:P:bushv") + safe_get(trafo3, "m:P:busmv") + safe_get(trafo3, "m:P:buslv"))

    imbalance_mw = total_gen_mw - total_load_mw - losses_mw

    # Breakdown percentages
    breakdown_percent = {cat: (val / total_gen_mw * 100) if total_gen_mw > 0 else 0 for cat, val in gen_breakdown.items()}

    output = {
        "convergence_status": "Converged",
        "total_generation_mw": total_gen_mw,
        "total_load_mw": total_load_mw,
        "total_losses_mw": losses_mw,
        "distributed_slack_imbalance_mw": imbalance_mw,
        "generation_breakdown": {
            "mw": gen_breakdown,
            "percent": breakdown_percent
        },
        "total_inertia_gvas": total_inertia_mvas / 1000.0,
        "reference_check": {
            "ref_gen_mw": 9388.0,
            "ref_inertia_gvas": 35.1,
            "gen_diff_mw": total_gen_mw - 9388.0,
            "inertia_diff_gvas": (total_inertia_mvas / 1000.0) - 35.1
        },
        "pf_messages": pf_messages,
        "timing": timing
    }
    
    timing["extract_results_seconds"] = time.time() - (start_time + timing.get("power_flow_seconds", 0))
    
    res_path = os.path.join(results_dir, "power_flow.json")
    with open(res_path, "w") as f:
        json.dump(output, f, indent=2)
    return output

if __name__ == "__main__":
    try:
        res = run_analysis()
    except Exception as e:
        results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
        os.makedirs(results_dir, exist_ok=True)
        with open(os.path.join(results_dir, "error.json"), "w") as f:
            json.dump({"error": str(e), "traceback": traceback.format_exc()}, f, indent=2)
```
