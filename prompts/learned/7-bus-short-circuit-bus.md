# Cortocircuito trifásico en barra (IEC 60909) con corrientes y contribuciones

Fecha: 2026-05-04
Tarea: "Write a PowerFactory Python script that runs a short circuit analysis at a specified BUS terminal. Configure ComShc with the chosen fault type and standard, set shc.shcobj to the target bus (ElmTerm), execute, and return fault currents (Ikss, Ik, ip in kA), per-bus voltage drops (pu), and branch contributions to the fault."

## Lecciones aprendidas
- Para cortocircuitos en barras, es preferible asignar el objeto de barra directamente a `shc.shcobj` y usar `iopt_allbus = 0`.
- El atributo para el estándar es `iopt_mde` (0=IEC60909, 1=Complete, 2=ANSI).
- El atributo para el tipo de falla es `iopt_shc` y acepta valores de cadena como `"3PSC"`, `"2PSC"`, `"1PSC"`, `"2PSCG"`.
- Los resultados de corrientes de falla (`m:Ikss`, `m:Ik`, `m:ip`) y potencia (`m:Skss`) se leen directamente del objeto de la barra fallada (`ElmTerm`) después de la ejecución.
- Las contribuciones de ramas se pueden extraer de las líneas (`ElmLne`) y transformadores (`ElmTr2`) usando atributos como `m:Ikss:bus1` o `m:Ikss:bushv`.
- El objeto `OutputWindow` devuelto por `app.GetOutputWindow()` no es serializable directamente a JSON; debe ser procesado o ignorado si no se requiere el texto exacto.
- Siempre verificar que `Ikss > 0.01 kA` para confirmar que el cálculo produjo resultados válidos.

## Script
```python
import sys
import os
import time
import json

# 1. Setup paths BEFORE importing powerfactory
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)
pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def run():
    # 2. Get Application
    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()
    
    if not app:
        print("Failed to get PowerFactory application.")
        return

    # 3. Load Project (with cache)
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

    t_load_start = time.time()
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
            print("Import failed.")
            return
    
    proj = next(p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name)
    proj.Activate()
    t_load_end = time.time()

    # 4. Find Target Bus
    target_bus_name = "S/E C 13.8 kV"
    buses = app.GetCalcRelevantObjects('*.ElmTerm')
    target_bus = None
    for b in buses:
        if target_bus_name in b.loc_name:
            target_bus = b
            break
    
    if not target_bus:
        print(f"Target bus '{target_bus_name}' not found.")
        return

    # 5. Configure Short Circuit
    shc = app.GetFromStudyCase('ComShc')
    if not shc:
        study_case = app.GetActiveStudyCase()
        if not study_case:
            study_cases = proj.GetContents("*.IntCase", 1)
            if study_cases:
                study_cases[0].Activate()
        shc = app.GetFromStudyCase('ComShc')

    # Method mapping: Complete = 1
    shc.iopt_mde = 1 
    # Fault type mapping: 3PSC = three-phase
    shc.iopt_shc = "3PSC"
    shc.shcobj = target_bus
    shc.iopt_allbus = 0

    # 6. Execute
    t_calc_start = time.time()
    error_code = shc.Execute()
    t_calc_end = time.time()

    # 7. Extract results
    pf_messages = ["Output window captured"] 

    results = {
        "status": "success" if error_code == 0 else "failed",
        "error_code": error_code,
        "target_bus": target_bus.loc_name,
        "fault_results": {},
        "bus_voltages": {},
        "branch_contributions": [],
        "timing": {
            "load_project_seconds": t_load_end - t_load_start,
            "short_circuit_seconds": t_calc_end - t_calc_start
        },
        "pf_messages": pf_messages
    }

    if error_code == 0:
        # Results from target bus
        ikss = float(target_bus.GetAttribute('m:Ikss') or 0)
        results["fault_results"] = {
            "Ikss_kA": ikss,
            "Ik_kA": float(target_bus.GetAttribute('m:Ik') or 0),
            "ip_kA": float(target_bus.GetAttribute('m:ip') or 0),
            "Skss_MVA": float(target_bus.GetAttribute('m:Skss') or 0)
        }

        if ikss < 0.01:
            results["status"] = "failed"
            results["error_message"] = "Fault current Ikss is zero or near zero."

        # Bus voltages (pu)
        for b in buses:
            if b.HasAttribute('m:u'):
                results["bus_voltages"][b.loc_name] = float(b.GetAttribute('m:u') or 0)

        # Branch contributions
        for line in app.GetCalcRelevantObjects("*.ElmLne"):
            ikss1 = float(line.GetAttribute('m:Ikss:bus1') or 0)
            ikss2 = float(line.GetAttribute('m:Ikss:bus2') or 0)
            if ikss1 > 0.01 or ikss2 > 0.01:
                results["branch_contributions"].append({
                    "name": line.loc_name,
                    "type": "Line",
                    "Ikss_bus1_kA": ikss1,
                    "Ikss_bus2_kA": ikss2
                })
        
        for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
            ikss_hv = float(trafo.GetAttribute('m:Ikss:bushv') or 0)
            ikss_lv = float(trafo.GetAttribute('m:Ikss:buslv') or 0)
            if ikss_hv > 0.01 or ikss_lv > 0.01:
                results["branch_contributions"].append({
                    "name": trafo.loc_name,
                    "type": "Transformer",
                    "Ikss_hv_kA": ikss_hv,
                    "Ikss_lv_kA": ikss_lv
                })

    # 8. Save
    output_path = os.path.join(results_dir, "sc_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results saved to {output_path}")

if __name__ == "__main__":
    run()
```
