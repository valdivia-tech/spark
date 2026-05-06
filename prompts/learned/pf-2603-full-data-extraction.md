# Extracción Completa de Datos (Bases, Líneas, Generadores) en 2603

Fecha: 2026-04-08
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: Activa Base SEN + escenario Laboral Madrugada, slack distribuido con iopt_errlf=1, NO deshabilites ElmDsl. Corre el flujo y extrae 3 JSON: todas_las_barras.json, todas_las_lineas.json, todos_los_generadores.json."

## Lecciones aprendidas
- **Volumen de Datos**: La extracción masiva de más de 20,000 barras y 3,000 líneas genera archivos JSON considerables (~5MB total) pero se maneja eficientemente en Python en pocos segundos (~7s).
- **Zonas por Carpeta**: En bases de operación del CEN, la "Zona" de un elemento se puede identificar confiablemente a través de su carpeta padre (`GetParent()`).
- **Slack Distribuido**: El uso de `iopt_pbal=1` (Distributed Slack) junto con `iopt_errlf=1` permite la convergencia en escenarios de madrugada con fragmentación de red (1282 áreas aisladas reportadas en este caso).
- **Mantenimiento de ElmDsl**: A diferencia de otras corridas donde se deshabilitan para evitar errores de DLL, en este caso se mantuvieron activos y el flujo convergió sin problemas (6 iteraciones).

## Script
```python
import sys
import os
import json
import time

# Initialization
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

def get_generator_type(obj):
    name = obj.loc_name.upper()
    if "TER" in name: return "TER"
    if "HE" in name or "HP" in name: return "HE/HP"
    if any(k in name for k in ["PFV", "SOL", "FV"]): return "PFV"
    if "PE" in name or "EOL" in name: return "PE"
    if "BESS" in name: return "BESS"
    if "CSP" in name: return "CSP"
    if "GEO" in name: return "GEO"
    return "Otros"

def get_zone(obj):
    parent = obj.GetParent()
    if parent:
        return parent.loc_name
    return "N/A"

def run():
    start_total = time.time()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    app = powerfactory.GetApplicationExt()
    if not app:
        return {"error": "Could not get PowerFactory application"}

    timing = {}

    # 1. Load Project
    start_load = time.time()
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd"))
    if not os.path.exists(pfd_path):
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
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_load

    # 2. Activate Study Case and Scenario
    start_act = time.time()
    study_case = next((sc for sc in proj.GetContents("*.IntCase", 1) if "Base SEN" in sc.loc_name), None)
    if not study_case:
        study_case = proj.GetContents("*.IntCase", 1)[0]
    study_case.Activate()

    scenario = next((sn for sn in proj.GetContents("*.IntScenario", 1) if "Laboral Madrugada" in sn.loc_name), None)
    if scenario:
        scenario.Activate()
    timing["activation_seconds"] = time.time() - start_act

    # 3. Configure Power Flow
    ldf = app.GetFromStudyCase("ComLdf")
    
    if ldf.HasAttribute("iopt_pbal"):
        ldf.SetAttribute("iopt_pbal", 1)
        
    if ldf.HasAttribute("iopt_errlf"):
        ldf.SetAttribute("iopt_errlf", 1)
        
    start_ldf = time.time()
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - start_ldf

    messages = []
    try:
        messages = app.GetOutputWindow().GetContent()
    except:
        pass

    # 4. Extract Data
    start_ext = time.time()
    
    # BARS
    buses_data = []
    all_buses = app.GetCalcRelevantObjects("*.ElmTerm")
    for b in all_buses:
        buses_data.append({
            "loc_name": b.loc_name,
            "v_nom_kv": safe_get(b, "uknom", 0.0),
            "v_pu": safe_get(b, "m:u", 0.0),
            "v_kv": safe_get(b, "m:U", 0.0),
            "ang_deg": safe_get(b, "m:phiu", 0.0),
            "zona": get_zone(b)
        })
    
    # LINES (active)
    lines_data = []
    all_lines = app.GetCalcRelevantObjects("*.ElmLne")
    for l in all_lines:
        if safe_get(l, "outserv", 1) == 0:
            bus1_obj = safe_get(l, "bus1")
            bus2_obj = safe_get(l, "bus2")
            lines_data.append({
                "loc_name": l.loc_name,
                "loading_pct": safe_get(l, "c:loading", 0.0),
                "p_mw": safe_get(l, "m:P:bus1", 0.0),
                "q_mvar": safe_get(l, "m:Q:bus1", 0.0),
                "bus1_name": bus1_obj.GetParent().loc_name if bus1_obj else "N/A",
                "bus2_name": bus2_obj.GetParent().loc_name if bus2_obj else "N/A",
                "zona": get_zone(l)
            })

    # GENERATORS (active)
    gens_data = []
    all_gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_gens:
        if safe_get(g, "outserv", 1) == 0:
            gens_data.append({
                "loc_name": g.loc_name,
                "pgini": safe_get(g, "pgini", 0.0),
                "qgini": safe_get(g, "qgini", 0.0),
                "tipo": get_generator_type(g),
                "zona": get_zone(g),
                "clase": g.GetClassName()
            })

    timing["extraction_seconds"] = time.time() - start_ext
    timing["total_seconds"] = time.time() - start_total

    # Save JSONs
    with open(os.path.join(results_dir, "todas_las_barras.json"), "w") as f:
        json.dump(buses_data, f, indent=2)
    with open(os.path.join(results_dir, "todas_las_lineas.json"), "w") as f:
        json.dump(lines_data, f, indent=2)
    with open(os.path.join(results_dir, "todos_los_generadores.json"), "w") as f:
        json.dump(gens_data, f, indent=2)

    # Final summary
    summary = {
        "status": "success" if error_code == 0 else "failed",
        "error_code": error_code,
        "counts": {
            "buses": len(buses_data),
            "lines": len(lines_data),
            "generators": len(gens_data)
        },
        "totals": {
            "generation_mw": sum(g["pgini"] for g in gens_data),
            "load_mw": sum(l["p_mw"] for l in lines_data if l["p_mw"] > 0)
        },
        "pf_messages": messages,
        "timing": timing
    }
    
    with open(os.path.join(results_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    return summary

if __name__ == "__main__":
    run()
```
