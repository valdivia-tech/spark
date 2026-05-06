# Extracción Completa de Datos 2603 (Sabado Madrugada)

Fecha: 2026-04-08
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: Activa Base SEN + escenario Sabado Madrugada, slack distribuido con iopt_errlf=1, NO deshabilites ElmDsl. Corre el flujo y extrae 3 JSON: barras, lineas y generadores."

## Lecciones aprendidas
- **Extracción Masiva de Datos**: En sistemas grandes (~20,000 barras), la extracción de atributos básicos (`uknom`, `m:u`, `m:phiu`) es eficiente si se realiza iterando sobre `GetCalcRelevantObjects`.
- **Nomenclatura de Conexión de Líneas**: Para obtener los nombres de las barras de conexión de una línea (`ElmLne`), se debe acceder a `line.bus1.cterm.loc_name` y `line.bus2.cterm.loc_name`.
- **Categorización por loc_name**: La clasificación de tecnología basada en prefijos/sufijos en `loc_name` (TER, HE, HP, PFV, PE, BESS, CSP, GEO) es el método más fiable en bases operativas del CEN donde no todos los atributos de tipo están poblados.
- **Configuración de Flujo**: El uso de `iopt_pbal = 4` (Slack distribuido) y `iopt_errlf = 1` (Continuar ante errores) permite la convergencia en modelos con fragmentación de red (1313 áreas aisladas detectadas) y modelos DSL con dependencias externas faltantes.

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

def get_tech_code(obj):
    name = obj.loc_name.upper()
    if "GEO" in name: return "GEO"
    if "BESS" in name: return "BESS"
    if "PFV" in name: return "PFV"
    if "CSP" in name: return "CSP"
    if "PE" in name: return "PE"
    if "TER" in name: return "TER"
    if "HE" in name: return "HE"
    if "HP" in name: return "HP"
    return "OTH"

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
    app.ClearOutputWindow()

    # 1. Load/Activate Project
    user = app.GetCurrentUser()
    project_internal_name = '2305-BD-Ovalle.12072023'
    pfd_filename = '2603-BD-OP-COORD-DMAP.pfd'
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", pfd_filename))

    cache_file = os.path.join(results_dir, ".project_cache.json")
    cache = {}
    if os.path.exists(cache_file):
        try:
            with open(cache_file) as f:
                cache = json.load(f)
        except:
            pass
            
    project_name = cache.get(pfd_filename)
    proj = None
    existing_projects = user.GetContents("*.IntPrj")
    
    if project_name:
        proj = next((p for p in existing_projects if p.loc_name == project_name), None)
    if not proj:
        proj = next((p for p in existing_projects if p.loc_name == project_internal_name), None)
    if not proj:
        proj = next((p for p in existing_projects if p.loc_name.startswith("2305-BD-Ovalle")), None)

    if not proj:
        projects_before = {p.loc_name for p in existing_projects}
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        
        existing_projects = user.GetContents("*.IntPrj")
        projects_after = {p.loc_name for p in existing_projects}
        new_projects = projects_after - projects_before
        if new_projects:
            project_name = list(new_projects)[0]
            proj = next((p for p in existing_projects if p.loc_name == project_name), None)
        else:
            proj = next((p for p in existing_projects if "Ovalle" in p.loc_name), None)
            if proj: project_name = proj.loc_name

    if not proj:
        return {"error": "Project not found"}

    if project_name:
        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)

    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_total
    
    # 2. Activate Study Case
    start_act = time.time()
    study_case = next((sc for sc in proj.GetContents("*.IntCase", 1) if sc.loc_name == "Base SEN"), None)
    if not study_case:
        cases = proj.GetContents("*.IntCase", 1)
        if cases: study_case = cases[0]
        else: return {"error": "No study case found"}
    study_case.Activate()
    
    # 3. Activate Scenario
    scenario = next((sn for sn in proj.GetContents("*.IntScenario", 1) if sn.loc_name == "Sabado Madrugada"), None)
    if scenario:
        scenario.Activate()
    timing["activation_seconds"] = time.time() - start_act

    # 4. Configure ComLdf
    ldf = app.GetFromStudyCase("ComLdf")
    if ldf.HasAttribute("iopt_pbal"): ldf.SetAttribute("iopt_pbal", 4) # Slack distribuido
    if ldf.HasAttribute("iopt_errlf"): ldf.SetAttribute("iopt_errlf", 1) # Continue on errors
        
    # 5. Execute
    start_ldf = time.time()
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - start_ldf

    pf_messages = []
    try:
        pf_messages = app.GetOutputWindow().GetContent()
    except:
        pass
    
    # 6. Extraction
    start_ext = time.time()
    
    # 6.1 BARRAS
    barras_data = []
    for b in app.GetCalcRelevantObjects("*.ElmTerm"):
        barras_data.append({
            "loc_name": b.loc_name,
            "v_nom_kv": safe_get(b, "uknom", 0.0),
            "v_pu": safe_get(b, "m:u", 0.0),
            "v_kv": safe_get(b, "m:U", 0.0),
            "ang_deg": safe_get(b, "m:phiu", 0.0),
            "zona": get_zone(b)
        })
    with open(os.path.join(results_dir, "todas_las_barras.json"), "w") as f:
        json.dump(barras_data, f, indent=2)

    # 6.2 LINEAS
    lineas_data = []
    for l in app.GetCalcRelevantObjects("*.ElmLne"):
        if safe_get(l, "outserv") == 0:
            bus1_name = "N/A"
            if hasattr(l, 'bus1') and l.bus1 and l.bus1.cterm:
                bus1_name = l.bus1.cterm.loc_name
            bus2_name = "N/A"
            if hasattr(l, 'bus2') and l.bus2 and l.bus2.cterm:
                bus2_name = l.bus2.cterm.loc_name
                
            lineas_data.append({
                "loc_name": l.loc_name,
                "loading_pct": safe_get(l, "c:loading", 0.0),
                "p_mw": safe_get(l, "m:P:bus1", 0.0),
                "q_mvar": safe_get(l, "m:Q:bus1", 0.0),
                "bus1_name": bus1_name,
                "bus2_name": bus2_name,
                "zona": get_zone(l)
            })
    with open(os.path.join(results_dir, "todas_las_lineas.json"), "w") as f:
        json.dump(lineas_data, f, indent=2)

    # 6.3 GENERADORES
    generadores_data = []
    tech_totals = {}
    for g in app.GetCalcRelevantObjects("*.ElmSym, *.ElmGenstat"):
        if safe_get(g, "outserv") == 0:
            tech = get_tech_code(g)
            p = safe_get(g, "pgini", 0.0)
            q = safe_get(g, "qgini", 0.0)
            
            generadores_data.append({
                "loc_name": g.loc_name,
                "pgini": p,
                "qgini": q,
                "tipo": tech,
                "zona": get_zone(g),
                "clase": g.GetClassName()
            })
            tech_totals[tech] = tech_totals.get(tech, 0.0) + p

    with open(os.path.join(results_dir, "todos_los_generadores.json"), "w") as f:
        json.dump(generadores_data, f, indent=2)

    timing["extract_results_seconds"] = time.time() - start_ext
    timing["total_seconds"] = time.time() - start_total
    
    summary = {
        "converged": (error_code == 0),
        "error_code": error_code,
        "project": proj.loc_name,
        "study_case": study_case.loc_name,
        "scenario": scenario.loc_name if scenario else "None",
        "counts": {
            "barras": len(barras_data),
            "lineas_activas": len(lineas_data),
            "generadores_activos": len(generadores_data)
        },
        "generation_summary_mw": tech_totals,
        "total_generation_mw": sum(tech_totals.values()),
        "pf_messages": pf_messages,
        "timing": timing
    }
    
    with open(os.path.join(results_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    return summary

if __name__ == "__main__":
    run()
```
