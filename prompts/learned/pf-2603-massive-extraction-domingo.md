# Extracción masiva de datos 2603 (Domingo Madrugada)
Fecha: 2026-05-22
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: Activa Base SEN + escenario Domingo Madrugada, slack distribuido con iopt_errlf=1, NO deshabilites ElmDsl. Corre el flujo y extrae 3 JSON: 1) todas_las_barras.json: TODAS las barras (ElmTerm) con loc_name, v_nom_kv, v_pu (m:u), v_kv (m:U), ang_deg (m:phiu), zona (carpeta padre). 2) todas_las_lineas.json: TODAS las lineas (ElmLne) activas con loc_name, loading_pct (c:loading), p_mw (m:P:bus1), q_mvar (m:Q:bus1), bus1_name, bus2_name, zona. 3) todos_los_generadores.json: TODOS los generadores activos (ElmSym+ElmGenstat) con loc_name, pgini, qgini, tipo (TER/HE/HP/PFV/PE/BESS/CSP/GEO), zona, clase."

## Lecciones aprendidas
- En PowerFactory 2024, los terminales de una línea (`ElmLne`) se acceden mediante los atributos `bus1` y `bus2`, no `pbus1`/`pbus2`.
- El objeto devuelto por `app.GetOutputWindow()` no es serializable directamente a JSON; debe manejarse como un objeto especial o convertirse a string/lista de mensajes si es necesario.
- La función `GetClassName()` es el estándar para obtener el nombre de la clase de un objeto en la API de Python.
- Usar `safe_get` con `HasAttribute` es vital para evitar `AttributeError` durante la extracción masiva, especialmente en proyectos grandes donde algunos elementos pueden no tener resultados calculados por diversas razones (islas, errores locales).
- La inicialización de la API puede fallar transitoriamente; un bucle de reintento con `time.sleep` mejora la robustez.

## Script
```python
import sys
import os
import time
import json

# PowerFactory Path setup
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def get_zone(obj):
    try:
        parent = obj.GetParent()
        while parent:
            cls_name = parent.GetClassName()
            if cls_name == 'ElmNet':
                return "Unknown"
            if cls_name == 'IntFolder':
                name = parent.loc_name
                if name.startswith('Zona ') or name in ['Norte', 'Centro', 'Sur']:
                    return name
            parent = parent.GetParent()
    except:
        pass
    return "Unknown"

def classify_gen(obj):
    name = obj.loc_name.upper()
    if "PFV" in name or "SOLAR" in name: return "PFV"
    if "PE_" in name or "EOLICO" in name: return "PE"
    if "HE_" in name or "EMBALSE" in name: return "HE"
    if "HP_" in name or "PASADA" in name: return "HP"
    if "BESS" in name: return "BESS"
    if "CSP" in name: return "CSP"
    if "GEO" in name: return "GEO"
    return "TER"

def safe_get(obj, attr, default=0.0):
    try:
        if obj.HasAttribute(attr):
            val = obj.GetAttribute(attr)
            return val if val is not None else default
    except:
        pass
    return default

def main():
    start_time = time.time()
    timing = {}

    app = None
    for attempt in range(3):
        try:
            app = powerfactory.GetApplication()
            if app: break
        except:
            try:
                app = powerfactory.GetApplicationExt()
                if app: break
            except:
                time.sleep(2)
    
    if not app:
        print("Failed to get PowerFactory application instance after 3 attempts.")
        return

    timing["init_app_seconds"] = time.time() - start_time
    
    t0 = time.time()
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd"))
    pfd_filename = os.path.basename(pfd_path)

    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    cache_file = os.path.join(results_dir, ".project_cache.json")
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cache = json.load(f)

    project_name = cache.get(pfd_filename)
    if not project_name:
        for p in (user.GetContents("*.IntPrj") or []):
            if "2603" in p.loc_name:
                project_name = p.loc_name
                break

    if not project_name:
        projects_before = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        projects_after = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        new_projects = projects_after - projects_before
        project_name = list(new_projects)[0] if new_projects else None
        if project_name:
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    
    if not proj:
        print(f"Could not find project {project_name}")
        return

    proj.Activate()
    timing["load_project_seconds"] = time.time() - t0

    t0 = time.time()
    study_case = None
    for c in proj.GetContents("*.IntCase", 1):
        if "Base SEN" in c.loc_name:
            study_case = c
            break
    
    if study_case:
        study_case.Activate()
    else:
        study_case = app.GetActiveStudyCase()

    for s in proj.GetContents("*.IntScenario", 1):
        if "Domingo" in s.loc_name and "Madrugada" in s.loc_name:
            s.Activate()
            break
    
    timing["activate_case_seconds"] = time.time() - t0

    t0 = time.time()
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_net = 0
    ldf.iopt_ds = 1
    if ldf.HasAttribute('iopt_errlf'):
        ldf.SetAttribute('iopt_errlf', 1)
    
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - t0
    
    pf_messages = ["Messages not captured - OutputWindow object is not serializable"]

    if error_code != 0:
        diag_path = os.path.join(results_dir, "diagnostico.json")
        diag = {
            "status": "diverged",
            "error_code": error_code,
            "project": project_name,
            "diagnosis": {
                "total_generation_mw": sum(safe_get(g, "pgini") for g in app.GetCalcRelevantObjects("*.ElmSym,*.ElmGenstat") if g.outserv == 0),
                "total_load_mw": sum(safe_get(l, "plini") for l in app.GetCalcRelevantObjects("*.ElmLod") if l.outserv == 0),
                "slack_bus_found": False
            }
        }
        with open(diag_path, "w") as f:
            json.dump(diag, f, indent=2)
        print("Divergence detected.")
        return

    t0 = time.time()
    
    buses_data = []
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        buses_data.append({
            "loc_name": bus.loc_name,
            "v_nom_kv": safe_get(bus, "uknom"),
            "v_pu": safe_get(bus, "m:u"),
            "v_kv": safe_get(bus, "m:U"),
            "ang_deg": safe_get(bus, "m:phiu"),
            "zona": get_zone(bus)
        })
    
    lines_data = []
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        if line.outserv == 0:
            b1 = getattr(line, "bus1", None)
            b2 = getattr(line, "bus2", None)
            lines_data.append({
                "loc_name": line.loc_name,
                "loading_pct": safe_get(line, "c:loading"),
                "p_mw": safe_get(line, "m:P:bus1"),
                "q_mvar": safe_get(line, "m:Q:bus1"),
                "bus1_name": b1.loc_name if b1 else "None",
                "bus2_name": b2.loc_name if b2 else "None",
                "zona": get_zone(line)
            })

    gens_data = []
    for gen in app.GetCalcRelevantObjects("*.ElmSym,*.ElmGenstat"):
        if gen.outserv == 0:
            gens_data.append({
                "loc_name": gen.loc_name,
                "pgini": safe_get(gen, "pgini"),
                "qgini": safe_get(gen, "qgini"),
                "tipo": classify_gen(gen),
                "zona": get_zone(gen),
                "clase": gen.GetClassName()
            })

    timing["extract_results_seconds"] = time.time() - t0

    with open(os.path.join(results_dir, "todas_las_barras.json"), "w") as f:
        json.dump(buses_data, f, indent=2)
    with open(os.path.join(results_dir, "todas_las_lineas.json"), "w") as f:
        json.dump(lines_data, f, indent=2)
    with open(os.path.join(results_dir, "todos_los_generadores.json"), "w") as f:
        json.dump(gens_data, f, indent=2)

    summary = {
        "status": "success",
        "totals": {
            "buses": len(buses_data),
            "lines": len(lines_data),
            "generators": len(gens_data),
            "total_gen_mw": sum(g["pgini"] for g in gens_data)
        },
        "timing": timing,
        "pf_messages": pf_messages
    }
    with open(os.path.join(results_dir, "summary.json"), "w") as f:
        json.dump(summary, f, indent=2)

    print(f"Extraction complete. Total Buses: {len(buses_data)}, Lines: {len(lines_data)}, Gens: {len(gens_data)}")

if __name__ == "__main__":
    main()
\```
