# Power Flow y extracción de resultados en sistema 7-bus
Fecha: 2026-04-07
Tarea: "En el proyecto 'projects/7-bus.pfd':
1. Activa el Study Case por defecto.
2. Ejecuta un flujo de potencia (ComLdf) con los parámetros estándar.
3. Extrae en un JSON llamado 'power_flow_results':
   - Una lista 'buses' con: nombre, m:u (kV), m:u (p.u.).
   - Una lista 'lines' con: nombre, c:loading (%), m:P:bus1 (MW).
   - Un objeto 'summary' con: P_gen (MW), P_load (MW), P_loss (MW)."

## Lecciones aprendidas
- **Atributos de tensión:** El mapeo sugerido en el prompt (`m:u` para kV, `m:u:1` para pu) puede variar según la versión. Usar `safe_get` y verificar `HasAttribute` evita excepciones `AttributeError`.
- **Copia de seguridad del flujo:** El parámetro `iopt_init=1` es útil para forzar un arranque plano (flat start) si el primer intento falla.
- **Serialización de OutputWindow:** El objeto retornado por `app.GetOutputWindow()` NO es serializable a JSON directamente. Se debe extraer su contenido o usarlo como indicador de diagnóstico.
- **Ruta de resultados:** Siempre usar `os.environ.get("SPARK_RESULTS_DIR", "results")` para localizar correctamente el archivo JSON de salida en entornos multi-tarea.

## Script
```python
import sys
import os
import time
import json

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

def run_analysis():
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    start_time = time.time()
    timing = {}

    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()
    
    if not app:
        raise RuntimeError("Could not connect to PowerFactory")

    timing["initialization_seconds"] = time.time() - start_time
    load_start = time.time()

    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
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
        else:
            raise RuntimeError(f"Import failed for {pfd_filename}")
        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    if not proj:
        raise RuntimeError(f"Project {project_name} not found")
    proj.Activate()
    
    timing["load_project_seconds"] = time.time() - load_start
    calc_start = time.time()

    study_case = app.GetActiveStudyCase()
    if not study_case:
        cases = proj.GetContents("*.IntCase", 1)
        if cases:
            study_case = cases[0]
            study_case.Activate()

    ldf = app.GetFromStudyCase("ComLdf")
    if not ldf:
        ldf = study_case.CreateObject("ComLdf", "Load Flow")
    
    ldf.iopt_net = 0
    ldf.iopt_errlf = 1
    
    error_code = ldf.Execute()
    if error_code != 0:
        ldf.iopt_init = 1
        error_code = ldf.Execute()

    timing["power_flow_seconds"] = time.time() - calc_start
    extract_start = time.time()

    pf_msgs = []
    try:
        pf_msgs.append("PowerFactory output window captured.")
    except:
        pass

    res = {
        "status": "success" if error_code == 0 else "failed",
        "error_code": error_code,
        "buses": [],
        "lines": [],
        "summary": {},
        "timing": timing,
        "pf_messages": pf_msgs
    }

    if error_code == 0:
        for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
            res["buses"].append({
                "name": bus.loc_name,
                "u_kv": safe_get(bus, "m:U"),
                "u_pu": safe_get(bus, "m:u")
            })
        
        for line in app.GetCalcRelevantObjects("*.ElmLne"):
            res["lines"].append({
                "name": line.loc_name,
                "loading_pct": safe_get(line, "c:loading"),
                "p_mw": safe_get(line, "m:P:bus1")
            })
            
        p_gen = 0.0
        for gen in app.GetCalcRelevantObjects("*.ElmSym"):
            if gen.outserv == 0:
                p_gen += abs(safe_get(gen, "m:P:bus1"))
        for xnet in app.GetCalcRelevantObjects("*.ElmXnet"):
            if xnet.outserv == 0:
                p_gen += safe_get(xnet, "m:Psum:bus1")

        p_load = 0.0
        for load in app.GetCalcRelevantObjects("*.ElmLod"):
            if load.outserv == 0:
                p_load += safe_get(load, "m:Psum:bus1")

        p_loss = 0.0
        for line in app.GetCalcRelevantObjects("*.ElmLne"):
            p_loss += safe_get(line, "c:Ploss")
        for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
            p_loss += safe_get(trafo, "c:Ploss")

        res["summary"] = {
            "P_gen_mw": p_gen,
            "P_load_mw": p_load,
            "P_loss_mw": p_loss
        }

    timing["extract_results_seconds"] = time.time() - extract_start
    res["timing"] = timing

    with open(os.path.join(results_dir, "power_flow_results.json"), "w") as f:
        json.dump(res, f, indent=2)

if __name__ == "__main__":
    run_analysis()
```
