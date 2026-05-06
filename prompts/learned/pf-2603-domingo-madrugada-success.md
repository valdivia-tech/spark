# Flujo de Potencia 'Domingo Madrugada' en Proyecto 2603

Fecha: 2026-04-07
Tarea: "En el proyecto '2603-BD-OP-COORD-DMAP.pfd': 1. Activar 'Base SEN'. 2. Activar escenario 'Domingo Madrugada'. 3. Configurar ComLdf con slack distribuido, flat start y iopt_errlf=1. 4. Correr flujo y reportar balance y desglose tecnológico."

## Lecciones aprendidas
- **Persistencia de Inicialización**: Tras fallos previos con la API de 2024 (Error 4002), el uso explícito de las rutas de PowerFactory 2026 Preview y su lógica de inicialización (`GetApplication` / `GetApplicationExt`) resultó exitoso.
- **Configuración de Robustez**: El parámetro `iopt_errlf = 1` es esencial en bases operativas del CEN para permitir que el flujo de potencia ignore errores de carga de DLLs de modelos dinámicos (DSL) que no están presentes en el entorno local, permitiendo cálculos estáticos correctos.
- **Desglose Tecnológico**: El uso de prefijos (`TER`, `GEO`, `HE`, `HP`, `PFV`, `CSP`, `PE`, `BESS`) permite mapear de forma precisa los elementos `ElmSym` y `ElmGenstat` a las categorías solicitadas por el operador.

## Script
```python
import sys
import os
import json
import time

# Initialization - Use PowerFactory 2026 logic from experiences
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
    
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()

    if not app:
        return {"error": "Could not get PowerFactory application"}

    timing = {}
    app.ClearOutputWindow()

    # 1. Load/Activate Project
    user = app.GetCurrentUser()
    project_internal_name = '2305-BD-Ovalle.12072023' # From experience
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
    
    # 2. Activate Study Case "Base SEN"
    start_act = time.time()
    study_case = next((sc for sc in proj.GetContents("*.IntCase", 1) if sc.loc_name == "Base SEN"), None)
    if not study_case:
        cases = proj.GetContents("*.IntCase", 1)
        if cases:
            study_case = cases[0]
        else:
            return {"error": "No study case found"}
        
    study_case.Activate()
    
    # 3. Activate Scenario "Domingo Madrugada"
    scenario = next((sn for sn in proj.GetContents("*.IntScenario", 1) if sn.loc_name == "Domingo Madrugada"), None)
    if scenario:
        scenario.Activate()
    timing["activation_seconds"] = time.time() - start_act

    # 4. Configure ComLdf
    ldf = app.GetFromStudyCase("ComLdf")
    # Distributed slack by synchronous generators
    if ldf.HasAttribute("iopt_pbal"): ldf.SetAttribute("iopt_pbal", 4)
    # Start option: Flat Start
    if ldf.HasAttribute("iopt_init"): ldf.SetAttribute("iopt_init", 1)
    # Continue on errors (DSL/DLL)
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
        
        # Collect from ElmSym
        for g in app.GetCalcRelevantObjects("*.ElmSym"):
            if safe_get(g, "outserv") == 0:
                p = safe_get(g, "m:P:bus1", 0.0)
                if abs(p) < 1e-6: p = safe_get(g, "Psum:bus", 0.0)
                total_gen_mw += p
                tech_breakdown[get_tech_breakdown(g)] += p
        
        # Collect from ElmGenstat
        for g in app.GetCalcRelevantObjects("*.ElmGenstat"):
            if safe_get(g, "outserv") == 0:
                p = safe_get(g, "m:P:bus1", 0.0)
                if abs(p) < 1e-6: p = safe_get(g, "Psum:bus", 0.0)
                total_gen_mw += p
                tech_breakdown[get_tech_breakdown(g)] += p
                
        # Collect from External Grids (Slack/Reference if any)
        for x in app.GetCalcRelevantObjects("*.ElmXnet"):
            if safe_get(x, "outserv") == 0:
                p = safe_get(x, "m:P:bus1", 0.0)
                total_gen_mw += p
                tech_breakdown["Otros"] += p

        total_load_mw = sum(safe_get(l, "m:P:bus1", 0.0) for l in app.GetCalcRelevantObjects("*.ElmLod") if safe_get(l, "outserv") == 0)
        reference_val = 8116.0
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
    output_file = os.path.join(results_dir, "power_flow_domingo_madrugada.json")
    with open(output_file, "w") as f:
        json.dump(res, f, indent=2)
```
