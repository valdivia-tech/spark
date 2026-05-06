# Flujo de potencia y reporte de tensiones/carga (7-bus)
Fecha: 2026-04-07
Tarea: "Importar proyecto 7-bus.pfd (usar cache), activar el study case disponible, correr flujo de potencia AC (ComLdf), extraer tensiones de barras y carga de líneas"

## Lecciones aprendidas
- **El objeto OutputWindow no es serializable directamente.** Al intentar guardarlo en un JSON, se produce un error. Se debe convertir a una lista de strings o usar `str()`. En este caso, se usó un bloque try-except para intentar iterar sobre él o convertirlo a string.
- **Evitar atributos inexistentes en ComLdf.** Algunos atributos sugeridos en los prompts (como `iopt_errlf`) pueden no estar presentes en todas las versiones de PowerFactory o en objetos `ComLdf` recién creados. Es mejor limitarse a los básicos (`iopt_net`, `iopt_at`, `iopt_asht`, `iopt_sim`, `iopt_lim`).
- **Uso de cache para proyectos.** El patrón de cache en `results/.project_cache.json` es fundamental para evitar duplicados al re-ejecutar scripts.

## Script
```python
import sys
import os
import json
import time

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

# 2. Load project using cache (avoid re-importing)
results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
os.makedirs(results_dir, exist_ok=True)

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
    # Verify the cached project still exists
    existing = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
    if project_name not in existing:
        project_name = None  # cache stale

if not project_name:
    # First time — import and detect the internal name
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
        raise RuntimeError(f"Import failed: no new project detected for {pfd_filename}")

    # Save to cache
    cache[pfd_filename] = project_name
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=2)

# Find and activate project object
proj = None
for p in (user.GetContents("*.IntPrj") or []):
    if p.loc_name == project_name:
        proj = p
        break

if not proj:
    raise RuntimeError(f"Could not find project {project_name} in user folder")

proj.Activate()
load_project_end = time.time()

# 3. Find study case (recursive) and activate
study_cases = proj.GetContents("*.IntCase", 1)
if not study_cases:
    raise RuntimeError("No study cases found in project")

study_case = study_cases[0]
study_case.Activate()

# 4. Run AC Load Flow
ldf = app.GetFromStudyCase("ComLdf")
ldf.iopt_net = 0      # AC load flow
ldf.iopt_at = 1       # Automatic tap adjustment
ldf.iopt_asht = 1     # Automatic shunt adjustment
ldf.iopt_sim = 0      # Balanced, positive sequence
ldf.iopt_lim = 1      # Reactive power limits

power_flow_start = time.time()
error_code = ldf.Execute()
power_flow_end = time.time()

# 5. Extract results
extract_start = time.time()
bus_voltages = []
line_loadings = []

if error_code == 0:
    # Bus voltages
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        if bus.HasAttribute("m:u"):
            bus_voltages.append({
                "name": bus.loc_name,
                "v_pu": bus.GetAttribute("m:u"),
                "v_kv": bus.GetAttribute("m:U"),
                "angle": bus.GetAttribute("m:phiu")
            })

    # Line loadings
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        if line.HasAttribute("c:loading"):
            line_loadings.append({
                "name": line.loc_name,
                "loading_pct": line.GetAttribute("c:loading"),
                "p_mw": line.GetAttribute("m:P:bus1"),
                "q_mvar": line.GetAttribute("m:Q:bus1")
            })
else:
    pass

extract_end = time.time()

# 6. Build final JSON
# Capture messages safely
pf_messages = []
try:
    ow = app.GetOutputWindow()
    # Try to iterate if it's a collection of messages
    for msg in ow:
        pf_messages.append(str(msg))
except:
    try:
        pf_messages = [str(app.GetOutputWindow())]
    except:
        pf_messages = ["Could not capture output window messages"]

results = {
    "status": "success" if error_code == 0 else "failed",
    "error_code": error_code,
    "bus_voltages": bus_voltages,
    "line_loadings": line_loadings,
    "pf_messages": pf_messages,
    "timing": {
        "load_project_seconds": load_project_end - start_time,
        "power_flow_seconds": power_flow_end - power_flow_start,
        "extract_results_seconds": extract_end - extract_start,
        "total_seconds": time.time() - start_time
    }
}

with open(os.path.join(results_dir, "7_bus_analysis.json"), "w") as f:
    json.dump(results, f, indent=2)

print(f"Task completed with status: {results['status']}")
```
