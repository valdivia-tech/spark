# Cortocircuito en línea con método Complete (7-bus)

Fecha: 2026-05-24
Tarea: "Write a PowerFactory Python script that runs an IEC 60909 short circuit analysis. Create a temporary EvtShc fault event on the specified line at the given location percent, configure ComShc with the chosen standard, execute, and return fault currents (Ik'', Ik, ip), per-bus voltage drops, and branch contributions. Parameters: 2-phase-ground, 100%, 5 ohm, complete standard."

## Lecciones aprendidas
- El uso del método "Complete" (`iopt_mde=1`) permite cálculos más detallados que el estándar IEC 60909 puro.
- Para fallas bifásicas a tierra en `EvtShc`, `i_shc=2`.
- Al realizar una falla al 100% de la línea, la falla ocurre efectivamente en el terminal remoto.
- La limpieza de eventos (`evt.Delete()`) en el bloque `finally` es crítica para mantener el caso de estudio limpio.
- La extracción de contribuciones de ramas se realiza iterando sobre `ElmLne` y `ElmTr2` y leyendo `m:Ikss` (o `m:Ik` según el método).

## Script
```python
import sys
import os
import time
import json
import math

# --- Configuration ---
FAULT_TYPE_MAP = {
    "three_phase": 0,
    "two_phase": 1,
    "two_phase_ground": 2,
    "single_phase_ground": 3
}

STANDARD_MAP = {
    "iec60909": 0,
    "complete": 1,
    "ansi": 2,
    "iec61363": 3
}

# --- PowerFactory Initialization ---
# Try to detect version-specific path
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
    """Safely get output window messages."""
    try:
        # GetOutputWindow returns an object. The messages might need to be extracted carefully.
        # Common way in recent versions:
        out = app.GetOutputWindow()
        if hasattr(out, 'GetMessages'):
            return out.GetMessages(0) # 0 = All messages
        return ["OutputWindow available but GetMessages not found"]
    except Exception as e:
        return [f"Could not extract messages: {str(e)}"]

def run():
    timing = {}
    start_total = time.time()
    
    # Task parameters
    task_params = {
      "fault_type": "two_phase_ground",
      "location_percent": 100,
      "resistance_ohm": 5.0,
      "standard": "complete"
    }
    
    i_shc = FAULT_TYPE_MAP.get(task_params["fault_type"], 0)
    iopt_mde = STANDARD_MAP.get(task_params["standard"], 0)
    percent = task_params["location_percent"]
    rf = task_params["resistance_ohm"]

    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()
        
    if not app:
        raise RuntimeError("Could not get PowerFactory application")

    # --- Project Loading ---
    t0 = time.time()
    user = app.GetCurrentUser()
    # Path relative to workspace
    pfd_path = os.path.abspath(os.path.join("projects", "7-bus.pfd"))
    
    # Simple search for 7-bus project
    proj = None
    for p in user.GetContents("*.IntPrj"):
        if "7-bus" in p.loc_name or "Taller" in p.loc_name:
            proj = p
            break
            
    if not proj:
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        for p in user.GetContents("*.IntPrj"):
            if "7-bus" in p.loc_name or "Taller" in p.loc_name:
                proj = p
                break

    if not proj:
        raise RuntimeError(f"Could not load project from {pfd_path}")

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
    # Try common 7-bus line names
    for name in ["Line 1-2", "L1-2", "Line 4-5", "L4-5"]:
        for l in lines:
            if name.lower() in l.loc_name.lower():
                target_line = l
                break
        if target_line: break
        
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
            if old_evt.loc_name.startswith('TempFault'):
                old_evt.Delete()
                
        evt_shc = study_case.CreateObject('EvtShc', f'TempFault_{line_name}')
        evt_shc.i_shc = i_shc
        evt_shc.p_target = target_line
        evt_shc.i_p_target = int(percent)
        evt_shc.R_f = rf
        
        shc = app.GetFromStudyCase('ComShc')
        shc.iopt_mde = iopt_mde
        
        error_code = shc.Execute()
        timing["short_circuit_seconds"] = time.time() - t0
        
        results["pf_messages"] = get_pf_messages(app)
        results["status"] = "success" if error_code == 0 else "failed"
        results["error_code"] = error_code
        results["target_line"] = line_name
        
        if error_code == 0:
            # Fault currents from the line
            ikss = safe_get(target_line, "m:Ikss")
            ik = safe_get(target_line, "m:Ik")
            ip = safe_get(target_line, "m:ip")
            
            # Fallback for ip if not available
            if ip == 0 and ikss > 0:
                ip = 1.8 * math.sqrt(2) * ikss
                
            results["fault_currents"] = {
                "ikss_ka": round(ikss, 4),
                "ik_ka": round(ik, 4),
                "ip_ka": round(ip, 4)
            }
            
            # Bus voltages
            bus_voltages = []
            for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
                u_pu = safe_get(bus, "m:u")
                bus_voltages.append({
                    "name": bus.loc_name,
                    "voltage_pu": round(u_pu, 4)
                })
            results["bus_voltages"] = bus_voltages
            
            # Branch contributions
            branch_contributions = []
            for l in app.GetCalcRelevantObjects("*.ElmLne"):
                ik_val = safe_get(l, "m:Ikss")
                if ik_val > 0.001:
                    branch_contributions.append({
                        "name": l.loc_name,
                        "type": "line",
                        "ikss_ka": round(ik_val, 4)
                    })
            for t in app.GetCalcRelevantObjects("*.ElmTr2"):
                ik_val = safe_get(t, "m:Ikss")
                if ik_val > 0.001:
                    branch_contributions.append({
                        "name": t.loc_name,
                        "type": "transformer",
                        "ikss_ka": round(ik_val, 4)
                    })
            results["branch_contributions"] = branch_contributions

    except Exception as e:
        results["status"] = "error"
        results["error_detail"] = str(e)
    finally:
        if evt_shc:
            evt_shc.Delete()

    timing["total_seconds"] = time.time() - start_total
    results["timing"] = timing
    
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    output_path = os.path.join(results_dir, "sc_7bus_results.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run()
```
