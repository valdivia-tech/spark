# Flujo de Potencia 'Sabado Madrugada' en Proyecto 2603

Fecha: 2026-04-07
Tarea: "Flujo de potencia Escenario 'Sabado Madrugada' en 2603-BD-OP-COORD-DMAP.pfd. Activar Study Case 'Base SEN', Activar escenario 'Sabado Madrugada' (IntScenario), Configurar ComLdf (slack distribuido, flat start, ignorar errores DSL). Calcular generación por tecnología."

## Lecciones aprendidas
- **Manejo de Prefijos Específicos**: El uso de prefijos como `BESS` para almacenamiento y `GEO` para geotermia (dentro de Térmica) permite una clasificación precisa de la matriz energética del SEN en bases operativas del CEN.
- **Robustez en la Importación**: Los proyectos del CEN a veces tienen nombres internos complejos (ej. `2305-BD-Ovalle.12072023` para el archivo `2603-BD-OP-COORD-DMAP.pfd`). Implementar una búsqueda recursiva por prefijo (`2305-BD-Ovalle*`) y por contenido (`"Ovalle" in p.loc_name`) asegura que el script no falle si el nombre interno varía ligeramente tras la importación.
- **Convergencia con DSL Activo**: A diferencia de otros escenarios con mayor estrés, 'Sabado Madrugada' converge sin problemas incluso con los modelos ElmDsl activos (`outserv=0`), siempre que se use `iopt_errlf=1` para ignorar fallos de carga de DLLs propietarias del CEN (como controladores de parques ERNC).
- **Consistencia de Datos**: El resultado obtenido (8,559 MW) muestra una desviación de apenas el 0.1% respecto al valor de referencia del CEN (8,568 MW), lo que valida que la activación del escenario y el cálculo con slack distribuido son correctos para este tipo de bases.

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

def get_tech_breakdown(obj):
    name = obj.loc_name.upper()
    if any(k in name for k in ["TER", "GEO"]):
        return "Térmica"
    if any(k in name for k in ["HE", "HP"]):
        return "Hidráulica"
    if any(k in name for k in ["PFV", "CSP"]):
        return "Solar"
    if "PE" in name:
        return "Eólica"
    if "BESS" in name:
        return "Almacenamiento"
    return "Otros"

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

    # Cache for project name
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
    
    # Try finding by cached name
    if project_name:
        proj = next((p for p in existing_projects if p.loc_name == project_name), None)
        
    # Try finding by known internal name
    if not proj:
        proj = next((p for p in existing_projects if p.loc_name == project_internal_name), None)
        
    # Try finding by prefix
    if not proj:
        proj = next((p for p in existing_projects if p.loc_name.startswith("2305-BD-Ovalle")), None)

    # Import if not found
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
            # Fallback search
            proj = next((p for p in existing_projects if "Ovalle" in p.loc_name or "2305-BD" in p.loc_name), None)
            if proj:
                project_name = proj.loc_name

    if not proj:
        available = [p.loc_name for p in existing_projects]
        return {"error": f"Project not found. Available: {available}"}

    # Save to cache
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
        if cases:
            study_case = cases[0]
        else:
            return {"error": "No study case found"}
        
    study_case.Activate()
    
    # 3. Activate Scenario
    scenario = next((sn for sn in proj.GetContents("*.IntScenario", 1) if sn.loc_name == "Sabado Madrugada"), None)
    if scenario:
        scenario.Activate()
    timing["activation_seconds"] = time.time() - start_act

    # 4. Configure ComLdf
    ldf = app.GetFromStudyCase("ComLdf")
    if ldf.HasAttribute("iopt_pbal"): ldf.SetAttribute("iopt_pbal", 4)
    if ldf.HasAttribute("iopt_init"): ldf.SetAttribute("iopt_init", 1)
    if ldf.HasAttribute("iopt_errlf"): ldf.SetAttribute("iopt_errlf", 1)
        
    # 5. Execute
    start_ldf = time.time()
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - start_ldf

    # Capture messages
    messages = []
    try:
        messages = app.GetOutputWindow().GetContent()
    except:
        pass
    
    results = {
        "converged": (error_code == 0),
        "error_code": error_code,
        "project": proj.loc_name,
        "study_case": study_case.loc_name,
        "scenario": scenario.loc_name if scenario else "None",
        "pf_messages": messages,
        "timing": timing
    }
    
    if error_code == 0:
        start_ext = time.time()
        tech_breakdown = {
            "Térmica": 0.0, "Hidráulica": 0.0, "Solar": 0.0, "Eólica": 0.0, "Almacenamiento": 0.0, "Otros": 0.0
        }
        total_gen_mw = 0.0
        
        for g in app.GetCalcRelevantObjects("*.ElmSym"):
            if safe_get(g, "outserv") == 0:
                p = safe_get(g, "m:P:bus1", 0.0)
                if abs(p) < 1e-6: p = safe_get(g, "Psum:bus", 0.0)
                total_gen_mw += p
                tech_breakdown[get_tech_breakdown(g)] += p
        
        for g in app.GetCalcRelevantObjects("*.ElmGenstat"):
            if safe_get(g, "outserv") == 0:
                p = safe_get(g, "m:P:bus1", 0.0)
                if abs(p) < 1e-6: p = safe_get(g, "Psum:bus", 0.0)
                total_gen_mw += p
                tech_breakdown[get_tech_breakdown(g)] += p
                
        for x in app.GetCalcRelevantObjects("*.ElmXnet"):
            if safe_get(x, "outserv") == 0:
                p = safe_get(x, "m:P:bus1", 0.0)
                total_gen_mw += p
                tech_breakdown["Otros"] += p

        total_load_mw = sum(safe_get(l, "m:P:bus1", 0.0) for l in app.GetCalcRelevantObjects("*.ElmLod") if safe_get(l, "outserv") == 0)
        reference_val = 8568.0
        results["results"] = {
            "generation_mw": {"total": total_gen_mw, "breakdown": tech_breakdown},
            "load_mw": total_load_mw,
            "losses_mw": total_gen_mw - total_load_mw,
            "validation": {
                "reference_mw": reference_val,
                "diff_mw": total_gen_mw - reference_val,
                "diff_percent": (total_gen_mw - reference_val) / reference_val * 100 if reference_val != 0 else 0
            }
        }
        timing["extract_results_seconds"] = time.time() - start_ext
    
    results["timing"]["total_seconds"] = time.time() - start_total
    return results

if __name__ == "__main__":
    res = run()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    output_file = os.path.join(results_dir, "power_flow.json")
    with open(output_file, "w") as f:
        json.dump(res, f, indent=2)
```
