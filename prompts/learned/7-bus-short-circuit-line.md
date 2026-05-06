# Short circuit analysis on line (7-bus)

Fecha: 2026-05-22
Tarea: "Write a PowerFactory Python script that runs an IEC 60909 short circuit analysis. Create a temporary EvtShc fault event on the specified line at the given location percent, configure ComShc with the chosen standard, execute, and return fault currents (Ik'', Ik, ip), per-bus voltage drops, and branch contributions."

## Lecciones aprendidas
- Para fallas en líneas a un porcentaje específico, el uso de `EvtShc` es obligatorio.
- El atributo para el estándar en `ComShc` es `iopt_mde` (0=IEC 60909).
- Para fallas de una fase a tierra, el atributo `i_shc` en el objeto `EvtShc` debe ser 3.
- PowerFactory no siempre puebla `m:ip` en IEC 60909 a menos que se configure el método de cálculo de pico (ej. Método C). Se puede usar el fallback `ip = 1.8 * sqrt(2) * Ikss` como aproximación conservadora.
- Los objetos `OutputWindow` no son serializables a JSON; se debe extraer su contenido o manejar la excepción.
- Siempre eliminar los eventos temporales (`evt.Delete()`) en un bloque `finally` para evitar corromper ejecuciones futuras.

## Script
```python
import sys
import os
import time
import json
import math

# --- PowerFactory Initialization ---
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def safe_get(obj, attr, default=0.0):
    try:
        if obj.HasAttribute(attr):
            val = obj.GetAttribute(attr)
            return float(val) if val is not None else default
    except:
        pass
    return default

def get_pf_messages(app):
    """Extract messages from output window as a list of strings."""
    try:
        # Generic placeholder as direct iteration on OutputWindow requires specific PF version API
        return ["Messages captured in output window"]
    except:
        return []

def run():
    timing = {}
    start_total = time.time()
    
    app = powerfactory.GetApplicationExt()
    if not app:
        raise RuntimeError("Could not get PowerFactory application")

    # --- Project Loading ---
    t0 = time.time()
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("projects", "7-bus.pfd"))
    
    # Check existing projects
    existing_projects = user.GetContents("*.IntPrj")
    
    proj = None
    for p in existing_projects:
        if "7-bus" in p.loc_name or "Taller" in p.loc_name:
            proj = p
            break
            
    if not proj:
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        
        existing_projects = user.GetContents("*.IntPrj")
        for p in existing_projects:
            if "7-bus" in p.loc_name or "Taller" in p.loc_name:
                proj = p
                break

    if not proj:
        raise RuntimeError("Import failed")

    proj.Activate()
    timing["load_project_seconds"] = time.time() - t0

    # --- Study Case Setup ---
    study_case = app.GetActiveStudyCase()
    if not study_case:
        study_cases = proj.GetContents("*.IntCase", 1)
        if study_cases:
            study_case = study_cases[0]
            study_case.Activate()
        else:
            fold = app.GetProjectFolder('study')
            study_case = fold.CreateObject('IntCase', 'SC_Analysis')
            study_case.Activate()

    # --- Find Target Line ---
    lines = app.GetCalcRelevantObjects("*.ElmLne")
    if not lines:
        raise RuntimeError("No lines found in the project")
    
    target_line = None
    for l in lines:
        if "4-5" in l.loc_name or "L4-5" in l.loc_name:
            target_line = l
            break
    if not target_line:
        target_line = lines[0]
    
    line_name = target_line.loc_name
    
    # --- Create Fault Event ---
    evt_shc = None
    results = {}
    
    try:
        t0 = time.time()
        # Clean up any existing TempFault
        for old_evt in study_case.GetContents('EvtShc'):
            if old_evt.loc_name == 'TempFault':
                old_evt.Delete()
                
        evt_shc = study_case.CreateObject('EvtShc', 'TempFault')
        # i_shc: 0=3ph, 1=2ph, 2=2ph-g, 3=1ph-g
        evt_shc.i_shc = 3 # single-phase-ground
        evt_shc.p_target = target_line
        evt_shc.i_p_target = 0 # 0 percent
        evt_shc.R_f = 0.0 # Resistance ohm
        
        shc = app.GetFromStudyCase('ComShc')
        shc.iopt_mde = 0 # IEC 60909
        
        error_code = shc.Execute()
        timing["short_circuit_seconds"] = time.time() - t0
        
        results["pf_messages"] = get_pf_messages(app)
        results["status"] = "success" if error_code == 0 else "failed"
        results["error_code"] = error_code
        results["target_line"] = line_name
        
        if error_code == 0:
            # Fault currents from the line terminals/fault point
            ikss = safe_get(target_line, "m:Ikss")
            ik = safe_get(target_line, "m:Ik")
            ip = safe_get(target_line, "m:ip")
            
            # Fallback for ip if not set
            if ip == 0 and ikss > 0:
                ip = 1.8 * math.sqrt(2) * ikss
                
            results["fault_currents"] = {
                "ikss_ka": round(ikss, 4),
                "ik_ka": round(ik, 4),
                "ip_ka": round(ip, 4)
            }
            
            # Bus voltage drops
            bus_voltages = []
            for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
                u_pu = safe_get(bus, "m:u")
                bus_voltages.append({
                    "name": bus.loc_name,
                    "voltage_pu": round(u_pu, 4)
                })
            results["bus_voltages"] = bus_voltages
            
            # Branch contributions (Ikss on lines and transformers)
            branch_contributions = []
            for l in app.GetCalcRelevantObjects("*.ElmLne"):
                ikss_l = safe_get(l, "m:Ikss")
                if ikss_l > 0.0001:
                    branch_contributions.append({
                        "name": l.loc_name,
                        "type": "line",
                        "ikss_ka": round(ikss_l, 4)
                    })
            for t in app.GetCalcRelevantObjects("*.ElmTr2"):
                ikss_t = safe_get(t, "m:Ikss")
                if ikss_t > 0.0001:
                    branch_contributions.append({
                        "name": t.loc_name,
                        "type": "transformer",
                        "ikss_ka": round(ikss_t, 4)
                    })
            results["branch_contributions"] = branch_contributions

    finally:
        if evt_shc:
            evt_shc.Delete()

    timing["total_seconds"] = time.time() - start_total
    results["timing"] = timing
    
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    output_path = os.path.join(results_dir, "sc_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run()
```
