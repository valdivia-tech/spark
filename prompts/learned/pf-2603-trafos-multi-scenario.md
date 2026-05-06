# Extracción Masiva de Transformadores por Escenario en 2603

Fecha: 2026-04-08
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd necesito TRANSFORMADORES para CADA uno de los 10 escenarios... extrae TODOS los transformadores (ElmTr2) activos con: loc_name, loading_pct, p_hv_mw, q_hv_mvar, bus_hv, bus_lv, zona."

## Lecciones aprendidas
- **Inicialización Crítica**: Llamar a `powerfactory.GetApplication()` seguido de `GetApplicationExt()` en el mismo proceso puede causar el error "PowerFactory cannot be started again in the same process" (Error 7000/4002). La solución más robusta en PowerFactory 2024 SP1 es llamar DIRECTAMENTE a `GetApplicationExt()` si no hay una instancia previa conocida.
- **Activación Secuencial**: En bases de operación del CEN, es necesario activar primero el `IntCase` base (ej. "Base SEN") y luego el `IntScenario` específico para asegurar que todos los datos de despacho y topología se carguen correctamente.
- **Identificación de Lado HV/LV**: Para transformadores de 2 devanados (`ElmTr2`), se puede identificar el lado de alta tensión (HV) comparando el atributo `uknom` (tensión nominal) de los terminales conectados a `bus1` y `bus2`.
- **Zonas y Jerarquía**: El atributo `zona` se extrajo del nombre de la carpeta padre (`GetParent().loc_name`) del elemento, lo cual es útil para agrupamiento geográfico o administrativo en modelos grandes.
- **Performance**: La extracción de ~880 transformadores por escenario tomó aproximadamente 3-4 segundos por iteración después de la activación inicial.

## Script
```python
import sys
import os
import json
import time

# Initialization
pf_path = r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12"
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

def get_zone(obj, proj):
    try:
        parent = obj.GetParent()
        if parent and parent != proj:
            return parent.loc_name
    except:
        pass
    return "Unknown"

def run_task():
    overall_start = time.time()
    timing = {}
    
    # Initialize PowerFactory - ONLY ONE CALL to GetApplicationExt()
    print("Connecting to PowerFactory...")
    try:
        app = powerfactory.GetApplicationExt()
    except Exception as e:
        print(f"Failed to connect: {e}")
        return
        
    if not app:
        print("Failed to get application.")
        return
        
    user = app.GetCurrentUser()
    print(f"Connected as: {user.loc_name}")
    
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd"))
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    # Project logic
    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if "2603-BD-OP-COORD-DMAP" in p.loc_name:
            proj = p
            break
            
    if not proj:
        print(f"Importing project from: {pfd_path}")
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        for p in (user.GetContents("*.IntPrj") or []):
            if "2603-BD-OP-COORD-DMAP" in p.loc_name:
                proj = p
                break

    if not proj:
        print("Project not found.")
        return

    proj.Activate()
    print(f"Project activated: {proj.loc_name}")
    
    scenario_names = [
        "Laboral Madrugada", "Laboral Diurno", "Laboral Vespertino",
        "Sabado Madrugada", "Sabado Diurno", "Sabado Vespertino",
        "Domingo Madrugada", "Domingo Diurno", "Domingo Vespertino",
        "ERNC CC"
    ]
    
    all_results = []
    
    # Collect cases and scenarios
    all_cases = proj.GetContents("*.IntCase", 1)
    all_scenarios = proj.GetContents("*.IntScenario", 1)
    
    base_case = next((c for c in all_cases if "Base SEN" in c.loc_name), None)
    if not base_case and all_cases:
        base_case = all_cases[0]

    for name in scenario_names:
        start_time = time.time()
        print(f"\n--- Scenario: {name} ---")
        
        # 1. Activate Base SEN
        if base_case:
            base_case.Activate()
            
        # 2. Activate Scenario
        scenario = next((s for s in all_scenarios if name.lower() in s.loc_name.lower()), None)
        if scenario:
            print(f"  Activating scenario: {scenario.loc_name}")
            scenario.Activate()
        else:
            # Maybe it's a study case itself?
            target_case = next((c for c in all_cases if name.lower() in c.loc_name.lower() and c != base_case), None)
            if target_case:
                print(f"  Activating study case: {target_case.loc_name}")
                target_case.Activate()
            else:
                print(f"  Warning: No specific scenario found for '{name}'")
            
        # 3. Configure and run LDF
        ldf = app.GetFromStudyCase("ComLdf")
        if not ldf:
            ldf = app.GetActiveStudyCase().CreateObject("ComLdf", "LDF")
        
        if ldf.HasAttribute("iopt_pbal"):
            ldf.SetAttribute("iopt_pbal", 4) # Distributed slack
        if ldf.HasAttribute("iopt_errlf"):
            ldf.SetAttribute("iopt_errlf", 1) # Continue on error
            
        error_code = ldf.Execute()
        
        # 4. Extract Transformers (ElmTr2)
        trafos = []
        all_tr2 = app.GetCalcRelevantObjects("*.ElmTr2")
        for t in all_tr2:
            if t.outserv == 1:
                continue
                
            # Attributes
            loading = safe_get(t, "c:loading", 0.0)
            p_hv = safe_get(t, "m:P:bushv", 0.0)
            q_hv = safe_get(t, "m:Q:bushv", 0.0)
            
            # Identify HV/LV buses
            bus_hv = "Unknown"
            bus_lv = "Unknown"
            try:
                b1 = t.bus1
                b2 = t.bus2
                if b1 and b2:
                    v1 = safe_get(b1, "uknom", 0.0)
                    v2 = safe_get(b2, "uknom", 0.0)
                    if v1 >= v2:
                        bus_hv = b1.loc_name
                        bus_lv = b2.loc_name
                    else:
                        bus_hv = b2.loc_name
                        bus_lv = b1.loc_name
            except:
                pass
                
            trafos.append({
                "loc_name": t.loc_name,
                "loading_pct": loading,
                "p_hv_mw": p_hv,
                "q_hv_mvar": q_hv,
                "bus_hv": bus_hv,
                "bus_lv": bus_lv,
                "zona": get_zone(t, proj)
            })
            
        all_results.append({
            "escenario": name,
            "error_code": error_code,
            "count": len(trafos),
            "transformadores": trafos
        })
        
        timing[name] = time.time() - start_time
        print(f"  Finished: {len(trafos)} active transformers. LDF={error_code}. Time={timing[name]:.2f}s")

    # Save to JSON
    output_path = os.path.join(results_dir, "transformadores_all_scenarios.json")
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
        
    final_counts = {res["escenario"]: res["count"] for res in all_results}
    print(f"\nEXTRACTED TOTAL. Counts: {json.dumps(final_counts)}")
    print(f"Total time: {time.time() - overall_start:.2f}s")

if __name__ == "__main__":
    run_task()
```
