# Load Flow 7-bus with Slack Assignment
Fecha: 2026-04-07
Tarea: "Activa el proyecto 'projects/7-bus.pfd' y realiza las siguientes tareas: 1. Activa el primer Study Case... 2. Identifica si existe un Slack Bus... 6. Reporta en un JSON..."

## Lecciones aprendidas
- **Atributos de Slack**: Los nombres de los atributos de control de despacho (`ip_ctrl`, `i_pqctrl`, `i_ctrl`) pueden variar según el tipo de elemento (`ElmSym`, `ElmXnet`, `ElmGenstat`). Usar una función `safe_set` y `safe_get` es fundamental para evitar fallos por atributos inexistentes.
- **OutputWindow**: `app.GetOutputWindow()` en PowerFactory 2026 devuelve un objeto `OutputWindow` que no es directamente serializable a JSON. Se debe verificar su tipo o convertirlo a string/lista de mensajes si el API lo permite.
- **Convergencia**: Para sistemas pequeños como el 7-bus, la convergencia es directa, pero el script incluye lógica de reintento con *flat start* (`iopt_init=1`) por robustez.
- **Resultados**: El balance de potencia (Gen: 14.03 MW, Load: 14.0 MW) indica que las pérdidas del sistema son mínimas (~0.03 MW).

## Script
```python
import sys
import os
import json
import time

# PowerFactory path setup
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

def safe_set(obj, attr, value):
    try:
        obj.SetAttribute(attr, value)
        return True
    except:
        return False

def run():
    timing = {}
    start_total = time.time()
    
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)
    
    if not app:
        return

    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
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
            return

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    
    if not proj:
        return
        
    start_activate = time.time()
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_activate

    study_case = app.GetActiveStudyCase()
    if not study_case:
        study_cases = proj.GetContents("*.IntCase", 1)
        if study_cases:
            study_cases[0].Activate()
            study_case = app.GetActiveStudyCase()
    
    if not study_case:
        return

    all_gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_gens:
        g.outserv = 0
    ext_grids = app.GetCalcRelevantObjects("*.ElmXnet")
    for x in ext_grids:
        x.outserv = 0

    slack_found = False
    for xnet in ext_grids:
        if safe_get(xnet, "i_pqctrl") == 0 or safe_get(xnet, "i_ctrl") == 0:
            slack_found = True
            break
    if not slack_found:
        for g in all_gens:
            if safe_get(g, "ip_ctrl") == 2 or safe_get(g, "i_ctrl") == 2:
                slack_found = True
                break
    if not slack_found:
        if ext_grids:
            if not safe_set(ext_grids[0], "i_pqctrl", 0):
                safe_set(ext_grids[0], "i_ctrl", 0)
        elif all_gens:
            all_gens.sort(key=lambda x: safe_get(x, "sgnom", 0.0) or safe_get(x, "pgini", 0.0), reverse=True)
            best_gen = all_gens[0]
            if not safe_set(best_gen, "ip_ctrl", 2):
                safe_set(best_gen, "i_ctrl", 2)

    ldf = app.GetFromStudyCase("ComLdf")
    safe_set(ldf, "iopt_net", 0)
    
    start_ldf = time.time()
    error = ldf.Execute()
    if error != 0:
        safe_set(ldf, "iopt_init", 1)
        error = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - start_ldf
    
    start_results = time.time()
    
    # Message collection attempt
    msgs = []
    try:
        ow = app.GetOutputWindow()
        if isinstance(ow, str):
            msgs = [ow]
        else:
            msgs = ["OutputWindow object captured (not serializable)"]
    except:
        msgs = ["Error capturing messages"]

    res = {
        "convergence": "Converged" if error == 0 else "Diverged",
        "error_code": error,
        "pf_messages": msgs,
        "buses": [],
        "lines": [],
        "summary": {
            "total_gen_mw": 0.0,
            "total_load_mw": 0.0
        }
    }
    
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        v_pu = safe_get(bus, "m:u", 0.0)
        u_nom = safe_get(bus, "uknom", 0.0)
        res["buses"].append({
            "name": bus.loc_name,
            "v_kv": v_pu * u_nom,
            "v_pu": v_pu
        })
        
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        loading = safe_get(line, "c:loading", 0.0)
        b1 = line.bus1.cterm.loc_name if line.bus1 and line.bus1.cterm else "N/A"
        b2 = line.bus2.cterm.loc_name if line.bus2 and line.bus2.cterm else "N/A"
        res["lines"].append({"name": line.loc_name, "loading_pct": loading, "bus1": b1, "bus2": b2})
        
    p_gen = 0.0
    for g in all_gens:
        if g.outserv == 0: p_gen += safe_get(g, "m:P:bus1", 0.0)
    for x in ext_grids:
        if x.outserv == 0: p_gen += safe_get(x, "m:P:bus1", 0.0)
    
    p_load = 0.0
    for l in app.GetCalcRelevantObjects("*.ElmLod"):
        if l.outserv == 0: p_load += safe_get(l, "m:P:bus1", 0.0)
        
    res["summary"]["total_gen_mw"] = p_gen
    res["summary"]["total_load_mw"] = p_load
    
    timing["extract_results_seconds"] = time.time() - start_results
    timing["total_seconds"] = time.time() - start_total
    res["timing"] = timing
    
    output_path = os.path.join(results_dir, "resultado_7bus.json")
    with open(output_path, "w") as f:
        json.dump(res, f, indent=2)
    print(f"Done. Saved to {output_path}")

if __name__ == "__main__":
    run()
```
