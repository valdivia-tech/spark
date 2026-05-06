# Flujo de Potencia con Relajación de Slack (2603 Laboral Diurno)

Fecha: 2026-04-07
Tarea: "En el proyecto 'projects/2603-BD-OP-COORD-DMAP.pfd': Activar Study Case 'Base SEN', Escenario 'Laboral Diurno', deshabilitar modelos dinámicos, relajar límites de TER ANGAMOS U1 (Slack) y ejecutar flujo de potencia."

## Lecciones aprendidas
- **Ruta del Proyecto**: El proyecto 2603 se encuentra en una subcarpeta `../projects/2603/`, no directamente en `../projects/`. Es importante verificar la estructura de directorios.
- **Relajación de Slack**: Definir 'TER ANGAMOS U1' como máquina de referencia (`ip_ctrl=2`) y relajar sus límites P/Q (+/- 99999) permite la convergencia en bases de operación que pueden tener desbalances significativos por redondeo o truncamiento de SCADA.
- **API de OutputWindow**: En PowerFactory 2024/2026, el método para obtener el contenido es `GetContent()`, no `GetMessages(0)`. Es recomendable usar `dir()` para verificar métodos si ocurre un `AttributeError`.
- **Desglose de Tecnologías**: El uso de patrones en `loc_name` y en el nombre del objeto contenedor (Parent) es efectivo para categorizar generadores en bases de datos grandes. Para el SEN Chileno, patrones como "HID", "SOL", "FV", "EOL", "TER" son fundamentales.
- **Filtro de Tensiones**: Es crítico filtrar barras con `u < 0.1 pu` al reportar tensiones bajas, ya que las bases de operación contienen cientos de barras fuera de servicio que aparecen con 0.0 pu.

## Script
```python
import sys
import os
import json
import time

# Initialization
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP2\Python\3.12")
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

def safe_set(obj, attr, val):
    try:
        if obj.HasAttribute(attr):
            obj.SetAttribute(attr, val)
            return True
    except:
        pass
    return False

def get_tech(obj):
    name = obj.loc_name.upper()
    parent = obj.GetParent()
    pname = parent.loc_name.upper() if parent else ""
    combined = name + " " + pname
    
    if any(k in combined for k in ["HID", "CH ", "CENTRAL HIDRAULICA"]):
        return "HID"
    if any(k in combined for k in ["SOL", "FV", "PHOTOVOLTAIC", "SOLAR"]):
        return "FV/SOL"
    if any(k in combined for k in ["EOL", "WIND", "PE ", "EOLICA"]):
        return "EOL"
    if any(k in combined for k in ["TER", "U1", "U2", "U3", "U4", "CTG", "TV", "TG", "ANGAMOS", "COCHRANE", "MEJILLONES", "VENTANAS", "GUACOLDA"]):
        return "TER"
    return "OTH"

def run():
    start_all = time.time()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)
    
    if not app:
        return {"error": "Could not get PowerFactory application"}

    timing = {}

    # 1. Load Project
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
    pfd_filename = os.path.basename(pfd_path)
    
    cache_file = os.path.join(results_dir, ".project_cache.json")
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache = json.load(f)
        except:
            pass

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
            return {"error": f"Import failed for {pfd_filename}"}
        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)

    proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
    if not proj:
        return {"error": "Project not found"}
    
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_all
    
    # 2. Activate Study Case and Scenario
    start_act = time.time()
    study_case = next((sc for sc in proj.GetContents("*.IntCase", 1) if sc.loc_name == "Base SEN"), None)
    if study_case:
        study_case.Activate()
    else:
        study_case = app.GetActiveStudyCase()
    
    scenario = next((sn for sn in proj.GetContents("*.IntScenario", 1) if sn.loc_name == "Laboral Diurno"), None)
    if scenario:
        scenario.Activate()
    timing["activation_seconds"] = time.time() - start_act

    # 3. Disable all ElmDsl
    for dsl in app.GetCalcRelevantObjects("*.ElmDsl"):
        dsl.outserv = 1
        
    # 4. Localize and modify slack 'TER ANGAMOS U1'
    slack_machine = None
    all_sym = app.GetCalcRelevantObjects("*.ElmSym")
    for sym in all_sym:
        if "TER ANGAMOS U1" in sym.loc_name:
            slack_machine = sym
            break
            
    if slack_machine:
        safe_set(slack_machine, "pg_max", 99999.0)
        safe_set(slack_machine, "pg_min", -99999.0)
        safe_set(slack_machine, "qg_max", 99999.0)
        safe_set(slack_machine, "qg_min", -99999.0)
        if not safe_set(slack_machine, "ip_ctrl", 2):
            safe_set(slack_machine, "i_ctrl", 2)
    
    # 5. Execute Power Flow
    start_ldf = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    if ldf.HasAttribute('iopt_errlf'):
        ldf.SetAttribute('iopt_errlf', 1)
        
    ldf.iopt_init = 1  # Flat start
    error_code = ldf.Execute()
    
    if error_code != 0:
        ldf.iopt_init = 0  # Snapshot retry
        error_code = ldf.Execute()
    
    timing["power_flow_seconds"] = time.time() - start_ldf
    
    messages = []
    try:
        messages = app.GetOutputWindow().GetContent()
    except Exception as e:
        messages = [f"Error getting messages: {str(e)}"]
    
    results = {
        "converged": (error_code == 0),
        "error_code": error_code,
        "slack_machine": slack_machine.loc_name if slack_machine else "Not found",
        "pf_messages": messages,
        "timing": timing
    }
    
    if error_code == 0:
        start_ext = time.time()
        
        # Generation summary
        sym_gens = app.GetCalcRelevantObjects("*.ElmSym")
        stat_gens = app.GetCalcRelevantObjects("*.ElmGenstat")
        
        p_sym = sum(safe_get(g, "m:P:bus1", 0.0) for g in sym_gens if not safe_get(g, "outserv"))
        p_stat = sum(safe_get(g, "m:P:bus1", 0.0) for g in stat_gens if not safe_get(g, "outserv"))
        p_xnet = sum(safe_get(x, "m:P:bus1", 0.0) for x in app.GetCalcRelevantObjects("*.ElmXnet") if not safe_get(x, "outserv"))
        
        # Tech breakdown
        tech_p = {"HID": 0.0, "TER": 0.0, "FV/SOL": 0.0, "EOL": 0.0, "OTH": 0.0}
        for g in sym_gens:
            if not safe_get(g, "outserv"):
                p = safe_get(g, "m:P:bus1", 0.0)
                tech = get_tech(g)
                tech_p[tech] += p
        for g in stat_gens:
            if not safe_get(g, "outserv"):
                p = safe_get(g, "m:P:bus1", 0.0)
                tech = get_tech(g)
                tech_p[tech] += p
        
        # Loads and Losses
        loads = app.GetCalcRelevantObjects("*.ElmLod")
        p_load = sum(safe_get(l, "m:P:bus1", 0.0) for l in loads if not safe_get(l, "outserv"))
        
        p_gen_total = p_sym + p_stat + p_xnet
        p_losses = p_gen_total - p_load
        p_losses_pct = (p_losses / p_gen_total * 100.0) if p_gen_total != 0 else 0.0
        
        # Top 10 Voltages
        buses = [b for b in app.GetCalcRelevantObjects("*.ElmTerm") if safe_get(b, "m:u", 0.0) > 0.1]
        buses_sorted = sorted(buses, key=lambda x: safe_get(x, "m:u", 0.0), reverse=True)
        
        top_v_high = [{
            "name": b.loc_name, "u_pu": safe_get(b, "m:u"), "u_kv": safe_get(b, "m:U")
        } for b in buses_sorted[:10]]
        
        top_v_low = [{
            "name": b.loc_name, "u_pu": safe_get(b, "m:u"), "u_kv": safe_get(b, "m:U")
        } for b in buses_sorted[-10:]][::-1]
        
        # Top 10 Loading
        lines = app.GetCalcRelevantObjects("*.ElmLne")
        lines_sorted = sorted(lines, key=lambda x: safe_get(x, "c:loading", 0.0), reverse=True)
        top_loading = [{
            "name": l.loc_name, "loading": safe_get(l, "c:loading")
        } for l in lines_sorted[:10]]
        
        results.update({
            "generation": {
                "total_mw": p_gen_total,
                "sym_mw": p_sym,
                "stat_mw": p_stat,
                "xnet_mw": p_xnet,
                "by_tech": tech_p
            },
            "load_and_losses": {
                "total_load_mw": p_load,
                "total_losses_mw": p_losses,
                "losses_pct": p_losses_pct
            },
            "top_voltages_high": top_v_high,
            "top_voltages_low": top_v_low,
            "top_line_loading": top_loading
        })
        
        timing["extract_results_seconds"] = time.time() - start_ext
    else:
        # Diagnosis
        buses = app.GetCalcRelevantObjects("*.ElmTerm")
        mismatch = sorted([b for b in buses if safe_get(b, "m:Pdiff") is not None], 
                         key=lambda x: abs(safe_get(x, "m:Pdiff", 0.0)), 
                         reverse=True)
        results["diagnosis"] = {
            "top_mismatch": [{
                "name": b.loc_name, "p_diff_mw": safe_get(b, "m:Pdiff"), "q_diff_mvar": safe_get(b, "m:Qdiff")
            } for b in mismatch[:5]]
        }

    timing["total_seconds"] = time.time() - start_all
    return results

if __name__ == "__main__":
    res = run()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    out_path = os.path.join(results_dir, "power_flow_results.json")
    with open(out_path, "w") as f:
        json.dump(res, f, indent=2)
```
