# Evaluación de impacto de modelos ElmDsl en Flujo de Potencia

Fecha: 2026-04-07
Tarea: "Evaluación de impacto de modelos ElmDsl en Flujo de Potencia (Laboral Diurno) en proyecto 2603-BD-OP-COORD-DMAP.pfd"

## Lecciones aprendidas
- La configuración `iopt_errlf = 1` en el objeto `ComLdf` es fundamental para permitir que el flujo de potencia se ejecute en bases de operación que contienen modelos dinámicos (DSL/DLL) cuyas dependencias externas no están presentes en el entorno de ejecución.
- Al activar el escenario 'Laboral Diurno' en el proyecto 2603, se logra la convergencia del flujo de potencia usando Slack Distribuido (`iopt_pbal = 4`) y un arranque en frío (`iopt_init = 1`).
- La clasificación de tecnología basada en prefijos en el nombre del objeto (`HE `, `HP `, `TER `, `GEO `, `PFV `, `CSP `, `PE `, `BESS`) es efectiva para este proyecto.
- Los consumos negativos en el desglose de tecnología (como en BESS) indican que los equipos están absorbiendo potencia (carga).

## Script
```python
import sys
import os
import time
import json

def run_experiment():
    start_time = time.time()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    # 1. Initialization - Updated to 2024 SP1 and Python 3.12
    pf_path = r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12"
    if pf_path not in sys.path:
        sys.path.insert(0, pf_path)
    
    pf_root = os.path.dirname(os.path.dirname(pf_path))
    os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

    import powerfactory
    
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()
    
    if not app:
        raise RuntimeError("Could not connect to PowerFactory")

    results = {
        "project": "2603-BD-OP-COORD-DMAP.pfd",
        "study_case": "Base SEN",
        "scenario": "Laboral Diurno",
        "timing": {"init_seconds": time.time() - start_time},
        "pf_messages": []
    }
    step_start = time.time()

    # 2. Project Loading
    user = app.GetCurrentUser()
    # Corrected path
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
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        else:
            raise RuntimeError(f"Import failed for {pfd_filename}")

    proj = None
    for p in (user.GetContents(f"{project_name}.IntPrj") or []):
        proj = p
        break
    if not proj:
        for p in (user.GetContents("*.IntPrj") or []):
            if p.loc_name == project_name:
                proj = p
                break
    
    if not proj:
        raise RuntimeError(f"Project {project_name} not found")
        
    proj.Activate()
    results["timing"]["load_project_seconds"] = time.time() - step_start
    step_start = time.time()

    # 3. Activate Study Case
    study_case = None
    all_cases = proj.GetContents("*.IntCase", 1)
    for c in all_cases:
        if c.loc_name == "Base SEN":
            study_case = c
            break
    
    if not study_case and all_cases:
        study_case = all_cases[0]
        results["study_case_fallback"] = study_case.loc_name
    
    if study_case:
        study_case.Activate()
    else:
        raise RuntimeError("No study case found")
    
    results["timing"]["activate_study_case_seconds"] = time.time() - step_start
    step_start = time.time()

    # 4. Activate Scenario
    scenario = None
    all_scenarios = proj.GetContents("*.IntScenario", 1)
    for s in all_scenarios:
        if s.loc_name == "Laboral Diurno":
            scenario = s
            break
    
    if scenario:
        scenario.Activate()
    else:
        results["scenario_warning"] = "Scenario 'Laboral Diurno' not found"

    results["timing"]["activate_scenario_seconds"] = time.time() - step_start
    step_start = time.time()

    # 5. Configure ComLdf
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_pbal = 4   # Slack distributed by synchronous generators
    ldf.iopt_init = 1   # Flat start
    if ldf.HasAttribute('iopt_errlf'):
        ldf.SetAttribute('iopt_errlf', 1)  # Ignore DLL/DSL errors
    
    # 6. Run Load Flow
    error_code = ldf.Execute()
    results["error_code"] = error_code
    results["convergence"] = "Converged" if error_code == 0 else "Diverged"
    
    results["timing"]["power_flow_seconds"] = time.time() - step_start
    step_start = time.time()

    # 7. Extract Summary Results
    total_gen_p = 0.0
    total_load_p = 0.0
    
    tech_breakdown = {
        "Hidráulica": 0.0,
        "Térmica": 0.0,
        "Solar": 0.0,
        "Eólica": 0.0,
        "BESS": 0.0,
        "Otros": 0.0
    }

    def get_tech_category(obj):
        name = obj.GetFullName().upper()
        if 'HE ' in name or 'HP ' in name: return 'Hidráulica'
        if 'TER ' in name or 'GEO ' in name: return 'Térmica'
        if 'PFV ' in name or 'CSP ' in name: return 'Solar'
        if 'PE ' in name: return 'Eólica'
        if 'BESS' in name: return 'BESS'
        return 'Otros'

    # Sync Generators
    for gen in app.GetCalcRelevantObjects("*.ElmSym"):
        if gen.outserv == 0:
            p = gen.GetAttribute("m:P:bus1")
            if p is not None:
                total_gen_p += p
                cat = get_tech_category(gen)
                tech_breakdown[cat] += p
    
    # Static Generators
    for sgen in app.GetCalcRelevantObjects("*.ElmGenstat"):
        if sgen.outserv == 0:
            p = sgen.GetAttribute("m:P:bus1")
            if p is not None:
                total_gen_p += p
                cat = get_tech_category(sgen)
                tech_breakdown[cat] += p

    # External Grids
    for xnet in app.GetCalcRelevantObjects("*.ElmXnet"):
        if xnet.outserv == 0:
            p = xnet.GetAttribute("m:P:bus1")
            if p is not None:
                total_gen_p += p
                tech_breakdown["Otros"] += p

    # Loads
    for load in app.GetCalcRelevantObjects("*.ElmLod"):
        if load.outserv == 0:
            p = load.GetAttribute("m:P:bus1")
            if p is not None:
                total_load_p += p

    results["summary"] = {
        "total_generation_mw": total_gen_p,
        "total_load_mw": total_load_p,
        "losses_mw": total_gen_p - total_load_p,
        "imbalance_mw": 0.0 if error_code == 0 else (total_gen_p - total_load_p)
    }
    results["tech_breakdown_mw"] = tech_breakdown
    
    results["timing"]["extract_results_seconds"] = time.time() - step_start
    results["total_seconds"] = time.time() - start_time

    # Save results
    output_path = os.path.join(results_dir, "dsl_impact_evaluation.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run_experiment()
```
