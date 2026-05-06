# Flujo de Potencia 7-bus con Asignación Automática de Slack
Fecha: 2026-04-07
Tarea: "Ejecutar flujo de potencia en 7-bus.pfd, asegurar existencia de slack, extraer resultados detallados de barras, líneas y resumen de potencia."

## Lecciones aprendidas
- **Asignación de Slack Dinámica:** Si el proyecto no tiene una Red Externa (`ElmXnet`) activa, se puede crear una dinámicamente en cualquier barra (`ElmTerm`) usando `bus.CreateObject("ElmXnet", "Name")` y estableciendo `bustp = "SL"`.
- **Cálculo de Balance Manual:** Para obtener el resumen de generación, carga y pérdidas, es confiable sumar los valores `m:P:bus1` de todos los elementos `ElmSym`, `ElmXnet` y `ElmLod` después de la convergencia.
- **Identificación de Barras en Líneas:** Para reportar las barras conectadas a una línea, se accede a `line.bus1.GetParent()` y `line.bus2.GetParent()`.

## Script
```python
import sys
import os
import json
import time

def run():
    # 1. Initialize PowerFactory
    start_time = time.time()
    pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
    if pf_path not in sys.path:
        sys.path.insert(0, pf_path)

    pf_root = os.path.dirname(os.path.dirname(pf_path))
    os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

    import powerfactory

    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt(None, None)

    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)

    # 2. Load project using cache
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
    proj.Activate()
    load_project_end = time.time()

    # 3. Activate study case
    study_cases = proj.GetContents("*.IntCase", 1)
    if not study_cases:
        raise RuntimeError("No study cases found")
    study_case = study_cases[0]
    study_case.Activate()

    # 4. Check for Slack (External Grid)
    xnets = app.GetCalcRelevantObjects("*.ElmXnet")
    slack_active = False
    for xn in xnets:
        if xn.outserv == 0:
            slack_active = True
            break
    
    if not slack_active:
        # Try to find a generator and set it as reference if possible, 
        # or just pick the first terminal and add an ElmXnet
        gens = app.GetCalcRelevantObjects("*.ElmSym")
        if gens:
            # Most simple way to ensure a slack: add an ElmXnet to the first bus we find
            bus = app.GetCalcRelevantObjects("*.ElmTerm")[0]
            new_xnet = bus.CreateObject("ElmXnet", "AutoSlack")
            new_xnet.bustp = "SL" # Slack
            print(f"Added AutoSlack to {bus.loc_name}")
        else:
            raise RuntimeError("No generators or buses found to assign slack")

    # 5. Execute Load Flow
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_net = 0      # AC load flow
    ldf.iopt_at = 1       # Automatic tap adjustment
    ldf.iopt_asht = 1     # Automatic shunt adjustment
    ldf.iopt_sim = 0      # Balanced
    ldf.iopt_lim = 1      # Reactive power limits
    ldf.iopt_errlf = 1    # Ignore DSL errors

    power_flow_start = time.time()
    error_code = ldf.Execute()
    
    # Retry with iopt_init=1 if it fails
    if error_code != 0:
        print("Initial load flow failed, retrying with iopt_init=1")
        ldf.iopt_init = 1
        error_code = ldf.Execute()
        
    power_flow_end = time.time()

    # 6. Extract Results
    extract_start = time.time()
    bus_table = []
    line_table = []
    summary = {
        "total_gen_mw": 0,
        "total_load_mw": 0,
        "losses_mw": 0
    }

    if error_code == 0:
        # Buses
        for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
            bus_table.append({
                "Nombre": bus.loc_name,
                "V_kV": round(bus.GetAttribute("m:U"), 3) if bus.HasAttribute("m:U") else 0,
                "V_pu": round(bus.GetAttribute("m:u"), 3) if bus.HasAttribute("m:u") else 0
            })

        # Lines
        for line in app.GetCalcRelevantObjects("*.ElmLne"):
            # Get terminals
            bus1 = line.bus1.GetParent().loc_name if line.bus1 else "N/A"
            bus2 = line.bus2.GetParent().loc_name if line.bus2 else "N/A"
            
            line_table.append({
                "Nombre": line.loc_name,
                "Carga_pct": round(line.GetAttribute("c:loading"), 2) if line.HasAttribute("c:loading") else 0,
                "Barras": f"{bus1} - {bus2}"
            })

        # Summary - Get from the calculation result object or sum manually
        # Summing generators
        total_p_gen = 0
        for g in app.GetCalcRelevantObjects("*.ElmSym"):
            if g.outserv == 0:
                total_p_gen += g.GetAttribute("m:P:bus1")
        for x in app.GetCalcRelevantObjects("*.ElmXnet"):
            if x.outserv == 0:
                total_p_gen += x.GetAttribute("m:P:bus1")
        
        # Summing loads
        total_p_load = 0
        for l in app.GetCalcRelevantObjects("*.ElmLod"):
            if l.outserv == 0:
                total_p_load += l.GetAttribute("m:P:bus1")
        
        summary["total_gen_mw"] = round(total_p_gen, 2)
        summary["total_load_mw"] = round(total_p_load, 2)
        summary["losses_mw"] = round(total_p_gen - total_p_load, 2)

    extract_end = time.time()

    # Capture messages
    pf_messages = []
    try:
        ow = app.GetOutputWindow()
        # On some versions ow is an object that needs to be converted
        pf_messages = [str(app.GetOutputWindow())]
    except:
        pf_messages = ["Could not capture output window"]

    results = {
        "status": "success" if error_code == 0 else "failed",
        "error_code": error_code,
        "bus_table": bus_table,
        "line_table": line_table,
        "summary": summary,
        "pf_messages": pf_messages,
        "timing": {
            "load_project_seconds": load_project_end - start_time,
            "power_flow_seconds": power_flow_end - power_flow_start,
            "extract_results_seconds": extract_end - extract_start,
            "total_seconds": time.time() - start_time
        }
    }

    output_path = os.path.join(results_dir, "resultado_7_bus.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    run()
```
