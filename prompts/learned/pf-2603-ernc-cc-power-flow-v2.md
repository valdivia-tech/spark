# Flujo de Potencia 'ERNC CC' en Proyecto 2603 con Clasificación Tecnológica (Sin Atributos Extendidos)

Fecha: 2026-04-07
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: 1. Activa 'Base SEN'. 2. Activa escenario 'ERNC CC'. 3. Configura ComLdf con slack distribuido, flat start e ignora errores DSL. 4. Ejecuta flujo. 5. Clasifica por prefijos."

## Lecciones aprendidas
- **Atributos de ComLdf en PF 2026 Preview**: En algunas versiones o configuraciones de PowerFactory 2026 Preview, los atributos estándar como `iopt_pbal`, `iopt_init` e `iopt_errlf` pueden no ser accesibles mediante `SetAttribute` en ciertos proyectos, lanzando un `AttributeError`. Es recomendable usar bloques `try-except` para evitar que el script falle y confiar en los ajustes pre-configurados del escenario si la modificación falla.
- **Validación de Escenario ERNC**: El escenario 'ERNC CC' presenta un despacho coherente con alta penetración solar (~5.2 GW) y carga de BESS (~ -865 MW), resultando en una generación total (~8.06 GW) muy cercana a la referencia de 8.1 GW.
- **Carga de BESS**: En escenarios de alta disponibilidad ERNC, los sistemas de almacenamiento (BESS) suelen actuar como carga (potencia negativa en generación), lo cual es físicamente correcto.

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
    base_name = os.path.splitext(os.path.basename(pfd_path))[0]
    
    all_projects = user.GetContents("*.IntPrj") or []
    project_obj = next((p for p in all_projects if p.loc_name == base_name or p.loc_name.startswith(base_name)), None)
    
    if not project_obj:
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        all_projects = user.GetContents("*.IntPrj") or []
        project_obj = next((p for p in all_projects if p.loc_name == base_name or p.loc_name.startswith(base_name)), None)

    if not project_obj:
        return {"error": "Project not found"}

    project_obj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # 2. Activate Study Case and Scenario
    step_start = time.time()
    all_cases = project_obj.GetContents("*.IntCase", 1)
    study_case = next((c for c in all_cases if "Base SEN" in c.loc_name), None)
    if not study_case:
        return {"error": "Study case 'Base SEN' not found"}
    
    study_case.Activate()
    
    all_scenarios = project_obj.GetContents("*.IntScenario", 1) + project_obj.GetContents("*.ElmScenario", 1)
    scenario = next((s for s in all_scenarios if "ERNC CC" in s.loc_name), None)
    if not scenario:
        return {"error": "Scenario 'ERNC CC' not found"}
    
    scenario.Activate()
    timing["activate_case_scenario_seconds"] = time.time() - step_start
    
    # 3. Configure and run power flow
    step_start = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    
    attrs_to_set = {
        "iopt_pbal": 4,
        "iopt_init": 1,
        "iopt_errlf": 1
    }
    
    set_status = {}
    for attr, val in attrs_to_set.items():
        try:
            ldf.SetAttribute(attr, val)
            set_status[attr] = True
        except Exception as e:
            set_status[attr] = str(e)
            
    if set_status.get("iopt_pbal") is not True:
        try:
            ldf.SetAttribute("iopt_pbal", 1)
            all_sym = app.GetCalcRelevantObjects("*.ElmSym")
            slack_gen = next((g for g in all_sym if "TER ANGAMOS U1" in g.loc_name.upper()), None)
            if slack_gen:
                slack_gen.i_cp_ctrl = 1
                set_status["manual_slack"] = True
        except:
            set_status["manual_slack"] = False

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
        all_loads = app.GetCalcRelevantObjects("*.ElmLode") + app.GetCalcRelevantObjects("*.ElmLod")
        
        total_gen_p = sum(safe_get(g, "pgini", 0.0) for g in all_sym if g.outserv == 0) + \
                      sum(safe_get(g, "pini", 0.0) for g in all_genstat if g.outserv == 0)
        total_load_p = sum(safe_get(l, "plini", 0.0) for l in all_loads if l.outserv == 0)
        
        diag = {
            "status": "diverged",
            "error_code": error_code,
            "project": project_obj.loc_name,
            "study_case": "Base SEN",
            "diagnosis": {
                "total_generation_mw": total_gen_p,
                "total_load_mw": total_load_p,
                "imbalance_mw": total_gen_p - total_load_p,
                "isolated_buses": len([b for b in app.GetCalcRelevantObjects("*.ElmTerm") if safe_get(b, "m:u", 0.0) == 0.0])
            },
            "recommendations": ["Check if scenario 'ERNC CC' applied correctly", "Check slack bus"]
        }
        with open(os.path.join(results_dir, "diagnostico.json"), "w") as f:
            json.dump(diag, f, indent=2)
        return {"diagnostico": diag, "pf_messages": pf_messages, "timing": timing, "set_status": set_status}

    # 5. Extract results
    step_start = time.time()
    tech_gen_mw = {
        "Térmica": 0.0,
        "Hidráulica": 0.0,
        "Solar": 0.0,
        "Eólica": 0.0,
        "Almacenamiento": 0.0,
        "Otros": 0.0
    }
    
    for g in app.GetCalcRelevantObjects("*.ElmSym"):
        if g.outserv == 0:
            tech = get_tech(g.loc_name)
            p_calc = safe_get(g, "m:P:bus1", 0.0)
            tech_gen_mw[tech] += p_calc

    for g in app.GetCalcRelevantObjects("*.ElmGenstat"):
        if g.outserv == 0:
            tech = get_tech(g.loc_name)
            p_calc = safe_get(g, "m:P:bus1", 0.0)
            tech_gen_mw[tech] += p_calc
            
    total_gen_mw = sum(tech_gen_mw.values())
    all_loads = app.GetCalcRelevantObjects("*.ElmLode") + app.GetCalcRelevantObjects("*.ElmLod")
    total_load_mw = sum(safe_get(l, "m:P:bus1", 0.0) for l in all_loads if l.outserv == 0)
    losses_mw = total_gen_mw - total_load_mw
    
    timing["extract_results_seconds"] = time.time() - step_start
    
    output = {
        "power_flow": {
            "status": "converged",
            "error_code": error_code,
            "summary": {
                "total_generation_mw": total_gen_mw,
                "total_load_mw": total_load_mw,
                "total_losses_mw": losses_mw,
                "reference_gen_mw": 8098.0,
                "deviation_from_reference_mw": total_gen_mw - 8098.0
            },
            "breakdown_by_category": tech_gen_mw
        },
        "pf_messages": pf_messages,
        "timing": timing,
        "set_status": set_status
    }
    return output

if __name__ == "__main__":
    results = run_task()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    filename = "power_flow.json" if "power_flow" in results else "failure_report.json"
    with open(os.path.join(results_dir, filename), "w") as f:
        json.dump(results, f, indent=2)
```
\```
