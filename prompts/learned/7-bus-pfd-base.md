# Flujo de potencia base en 7-bus.pfd (Sin Study Case previo)
Fecha: 2026-04-07
Tarea: "Importar el proyecto 'projects/7-bus.pfd', activar el proyecto, ejecutar un flujo de potencia equilibrado (ComLdf), y extraer resultados de barras y líneas."

## Lecciones aprendidas
- **Atributos de pérdidas en líneas:** El atributo `c:Plos` no siempre está disponible para extracción directa a través de `GetAttribute` en todos los contextos. Una alternativa robusta es sumar las potencias activas que entran por ambos extremos de la línea (`m:P:bus1` + `m:P:bus2`), lo cual según la convención de signos de PowerFactory representa la potencia disipada (pérdidas).
- **Manejo de proyectos sin Study Case activo:** PowerFactory requiere que un caso de estudio (`IntCase`) esté activo para ejecutar comandos de cálculo como `ComLdf`. Si el proyecto no tiene uno por defecto, se debe buscar uno existente recursivamente o crear uno temporal para permitir la ejecución.
- **Validación de resultados:** Para el sistema de 7 barras (Taller 2), los valores esperados son aproximadamente 14.1 MW de generación y 14 MW de carga, lo cual se confirmó en la ejecución.

## Script
```python
import sys
import os
import json
import time

def run():
    start_time = time.time()
    
    # PowerFactory initialization
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

    if app is None:
        print("Failed to get PowerFactory application.")
        return

    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)

    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
    pfd_filename = os.path.basename(pfd_path)

    # Project import/activation logic with cache
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
        else:
            project_name = "Taller 2" # Probable internal name for 7-bus
        
        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break

    if not proj:
        projects = user.GetContents("*.IntPrj")
        if projects:
            proj = projects[0]
        else:
            print("Could not find or import project")
            return

    proj.Activate()
    load_project_end = time.time()

    # Find study case
    study_case = app.GetActiveStudyCase()
    if not study_case:
        cases = proj.GetContents("*.IntCase", 1)
        if cases:
            study_case = cases[0]
            study_case.Activate()
        else:
            # Create a temporary study case to hold the load flow command
            study_case = proj.CreateObject("IntCase", "Temp Case")
            study_case.Activate()

    # Balanced Load Flow
    ldf = app.GetFromStudyCase("ComLdf")
    if not ldf:
        ldf = study_case.CreateObject("ComLdf", "Load Flow")
    
    ldf.iopt_net = 0      # AC load flow
    ldf.iopt_sim = 0      # Balanced, positive sequence
    ldf.iopt_at = 1       # Automatic tap adjustment
    ldf.iopt_asht = 1     # Automatic shunt adjustment
    ldf.iopt_lim = 1      # Reactive power limits

    power_flow_start = time.time()
    error_code = ldf.Execute()
    power_flow_end = time.time()

    # Result extraction
    extract_start = time.time()
    bus_results = []
    line_results = []
    
    total_gen_mw = 0.0
    total_load_mw = 0.0

    if error_code == 0:
        # Buses
        for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
            bus_results.append({
                "nombre": bus.loc_name,
                "v_pu": bus.GetAttribute("m:u"),
                "v_kv": bus.GetAttribute("m:U")
            })
            
        # Lines
        for line in app.GetCalcRelevantObjects("*.ElmLne"):
            loading = line.GetAttribute("c:loading")
            i_ka = line.GetAttribute("m:I:bus1")
            
            # Active power flow at both ends to calculate losses
            p1 = line.GetAttribute("m:P:bus1")
            p2 = line.GetAttribute("m:P:bus2")
            
            # Sum of power entering the line = losses (PF uses sign convention)
            losses = 0.0
            if p1 is not None and p2 is not None:
                losses = p1 + p2
            
            line_results.append({
                "nombre": line.loc_name,
                "loading_pct": loading,
                "current_ka": i_ka,
                "losses_mw": losses
            })

        # Generators & Loads
        for gen in app.GetCalcRelevantObjects("*.ElmSym"):
            if gen.outserv == 0:
                p = gen.GetAttribute("m:P:bus1")
                if p: total_gen_mw += p
        for xnet in app.GetCalcRelevantObjects("*.ElmXnet"):
            if xnet.outserv == 0:
                p = xnet.GetAttribute("m:P:bus1")
                if p: total_gen_mw += p
        for lod in app.GetCalcRelevantObjects("*.ElmLod"):
            if lod.outserv == 0:
                p = lod.GetAttribute("m:P:bus1")
                if p: total_load_mw += p

    extract_end = time.time()

    # Capture messages
    pf_messages = []
    try:
        ow = app.GetOutputWindow()
        # On some systems, GetOutputWindow doesn't return a string-convertible object directly
        # but we'll try it.
        pf_messages = [str(ow)]
    except:
        pass

    final_results = {
        "status": "success" if error_code == 0 else "failed",
        "error_code": error_code,
        "project": proj.loc_name,
        "summary": {
            "total_gen_mw": total_gen_mw,
            "total_load_mw": total_load_mw,
            "total_losses_mw": total_gen_mw - total_load_mw
        },
        "bus_voltages": bus_results,
        "line_loading": line_results,
        "pf_messages": pf_messages,
        "timing": {
            "load_project_seconds": load_project_end - start_time,
            "power_flow_seconds": power_flow_end - power_flow_start,
            "extract_results_seconds": extract_end - extract_start,
            "total_seconds": time.time() - start_time
        }
    }

    results_path = os.path.join(results_dir, "power_flow_results.json")
    with open(results_path, "w") as f:
        json.dump(final_results, f, indent=2)

if __name__ == "__main__":
    run()
```
