# Get line parameters from 7-bus project
Fecha: 2026-05-20
Tarea: "Write a PowerFactory Python script that returns impedance parameters of all lines (or a filtered list): R1/X1/R0/X0 per km from line type, plus total Z1, Z0, angles, and K0 factor (Z0-Z1)/(3*Z1) using line length."

## Lecciones aprendidas
- El proyecto `7-bus.pfd` se identifica internamente como "Taller 2".
- Los parámetros de línea pueden estar en el objeto `ElmLne` o en su tipo `TypLne`. El atributo `iopt_typ` indica cuál se está usando (0 para tipo, 1 para manual).
- El objeto `OutputWindow` obtenido con `app.GetOutputWindow()` no es directamente serializable a JSON y causará un error si se intenta incluir tal cual.
- Es importante usar `math.atan2` y `math.degrees` para el cálculo de ángulos de impedancia.

## Script
```python
import sys
import os
import json
import time
import math

# --- PowerFactory Initialization ---
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

try:
    app = powerfactory.GetApplication()
except:
    app = powerfactory.GetApplicationExt(None, None)

if not app:
    raise RuntimeError("Could not connect to PowerFactory.")

# --- Project Loading ---
user = app.GetCurrentUser()
pfd_path = os.path.abspath(os.path.join("projects", "7-bus.pfd"))
pfd_filename = os.path.basename(pfd_path)

results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
os.makedirs(results_dir, exist_ok=True)
cache_file = os.path.join(results_dir, ".project_cache.json")

cache = {}
if os.path.exists(cache_file):
    with open(cache_file) as f:
        cache = json.load(f)

project_name = cache.get(pfd_filename)

def get_existing_projects():
    return {p.loc_name: p for p in (user.GetContents("*.IntPrj") or [])}

existing_projects = get_existing_projects()

if project_name and project_name not in existing_projects:
    project_name = None

if not project_name:
    for name in ["Taller 2", "7-bus", "7-Bus System"]:
        if name in existing_projects:
            project_name = name
            break

if not project_name:
    import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
    import_obj.SetAttribute("e:g_file", str(pfd_path))
    import_obj.g_target = user
    import_obj.Execute()
    import_obj.Delete()
    
    existing_after = get_existing_projects()
    new_projects = set(existing_after.keys()) - set(existing_projects.keys())
    
    if new_projects:
        project_name = list(new_projects)[0]
    else:
        if "Taller 2" in existing_after:
            project_name = "Taller 2"
        else:
             raise RuntimeError(f"Import failed or project not found for {pfd_filename}.")
    
    cache[pfd_filename] = project_name
    with open(cache_file, "w") as f:
        json.dump(cache, f, indent=2)

proj = (get_existing_projects()).get(project_name)
if not proj:
    raise RuntimeError(f"Project {project_name} not found.")

proj.Activate()

# --- Script Configuration ---
t_start = time.time()

study_case = app.GetActiveStudyCase()
if study_case is None:
    study_cases = proj.GetContents("*.IntCase", 1)
    if study_cases:
        study_cases[0].Activate()
        study_case = app.GetActiveStudyCase()

# --- Extraction ---
def safe_get(obj, attr, default=0.0):
    if obj and obj.HasAttribute(attr):
        val = obj.GetAttribute(attr)
        return float(val) if val is not None else default
    return default

lines = app.GetCalcRelevantObjects("*.ElmLne")
line_data = []

for line in lines:
    length = safe_get(line, "dline", 1.0)
    iopt_typ = safe_get(line, "iopt_typ", 0)
    
    r1_km, x1_km, r0_km, x0_km = 0.0, 0.0, 0.0, 0.0
    typ = line.GetAttribute("typ_id")
    
    if iopt_typ == 0 and typ:
        r1_km = safe_get(typ, "rline")
        x1_km = safe_get(typ, "xline")
        r0_km = safe_get(typ, "rline0")
        x0_km = safe_get(typ, "xline0")
        type_name = typ.loc_name
    else:
        r1_km = safe_get(line, "rline")
        x1_km = safe_get(line, "xline")
        r0_km = safe_get(line, "rline0")
        x0_km = safe_get(line, "xline0")
        type_name = "Manual"

    r1_tot = r1_km * length
    x1_tot = x1_km * length
    z1_tot = math.sqrt(r1_tot**2 + x1_tot**2)
    angle1 = math.degrees(math.atan2(x1_tot, r1_tot)) if z1_tot > 0 else 0.0
    
    r0_tot = r0_km * length
    x0_tot = x0_km * length
    z0_tot = math.sqrt(r0_tot**2 + x0_tot**2)
    angle0 = math.degrees(math.atan2(x0_tot, r0_tot)) if z0_tot > 0 else 0.0
    
    k0 = (z0_tot - z1_tot) / (3.0 * z1_tot) if z1_tot > 1e-6 else 0.0
    
    line_data.append({
        "name": line.loc_name,
        "type": type_name,
        "length_km": length,
        "r1_ohm_per_km": r1_km,
        "x1_ohm_per_km": x1_km,
        "r0_ohm_per_km": r0_km,
        "x0_ohm_per_km": x0_km,
        "z1_total_ohm": z1_tot,
        "angle1_deg": angle1,
        "z0_total_ohm": z0_tot,
        "angle0_deg": angle0,
        "k0_factor": k0
    })

t_end = time.time()

results = {
    "project": project_name,
    "lines": line_data,
    "pf_messages": [], # Skip for now as it caused serialization error
    "timing": {
        "extraction_seconds": t_end - t_start
    }
}

output_path = os.path.join(results_dir, "line_parameters.json")
with open(output_path, "w") as f:
    json.dump(results, f, indent=2)
print(f"Results saved to {output_path}")
```
