# Extracción de Datos Geográficos y Activos en Escenario ERNC (CEN 2604)
Fecha: 2026-05-06
Tarea: "Flujo de potencia y extracción de datos en escenario 'Penetracion ERNC CC' de la BD 2604, reportando transformadores y generación agregada por zona."

## Lecciones aprendidas
- **Consistencia con Receta 2604**: Seguir exactamente los parámetros `iopt_init=1`, `iopt_pbal=4`, `iopt_errlf=1` asegura convergencia en bases operacionales complejas (snapshots de SCADA).
- **Mapeo de Zonas**: El "parent walk" hasta encontrar prefijos numéricos (`00-`, `01-`, etc.) en carpetas `IntFolder` es el método más fiable para asignar ubicación geográfica a elementos en bases del CEN.
- **Eficiencia**: Evitar el "parent walk" para miles de transformadores o barras; limitarlo a generadores (~1,200) mantiene el tiempo de ejecución bajo 10 segundos.
- **Acceso a Atributos**: Confirmado una vez más que `m:P:bus1`, `m:P:bushv`, etc., deben accederse mediante `GetAttribute`.

## Script
```python
import sys, os, json, time

# --- PowerFactory init ---
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

RESULTS_DIR = os.environ.get("SPARK_RESULTS_DIR", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

def safe_get(obj, attr, default=None):
    try:
        if obj.HasAttribute(attr):
            val = obj.GetAttribute(attr)
            if val is None: return default
            if isinstance(val, (int, float)): return val
            if hasattr(val, 'loc_name'): return val.loc_name
            return str(val)
    except:
        pass
    return default

# --- Zone Mapping ---
ZONE_CONFIG = {
    '00-Norte Grande': {'name': 'Norte Grande', 'lat': -22.5, 'lng': -69.5},
    '01-Atacama': {'name': 'Atacama', 'lat': -27.0, 'lng': -70.0},
    '02-Coquimbo': {'name': 'Coquimbo', 'lat': -30.0, 'lng': -71.0},
    '03-Chilquinta-Aconcagua': {'name': 'Valparaíso', 'lat': -32.8, 'lng': -71.3},
    '04-Enel Distribución': {'name': 'Santiago', 'lat': -33.45, 'lng': -70.6},
    '05-Colbún': {'name': 'O\'Higgins', 'lat': -34.3, 'lng': -70.9},
    '06-Troncal_Qui-Cha': {'name': 'Maule', 'lat': -35.7, 'lng': -71.2},
    '07-Sistema154 - 66 kV (Centro)': {'name': 'Centro', 'lat': -34.8, 'lng': -71.5},
    '08-Charrúa': {'name': 'Biobío', 'lat': -37.0, 'lng': -72.5},
    '09-Concepción': {'name': 'Concepción', 'lat': -36.8, 'lng': -73.0},
    '10-Araucanía': {'name': 'Araucanía', 'lat': -38.7, 'lng': -72.5},
    '11-Araucanía 66 kV': {'name': 'Araucanía', 'lat': -38.7, 'lng': -72.5},
}

def find_zone(obj):
    cur = obj.GetParent()
    while cur is not None:
        name = cur.loc_name
        for prefix, config in ZONE_CONFIG.items():
            if name.startswith(prefix):
                return config['name']
        cur = cur.GetParent()
    return "Norte Grande"

# --- Project loading ---
t_load_start = time.time()
user = app.GetCurrentUser()
pfd_path = os.path.abspath(os.path.join("..", "projects", "2604", "2604-BD-OP-COORD-DMAP.pfd"))
pfd_filename = os.path.basename(pfd_path)

cache_file = os.path.join(RESULTS_DIR, ".project_cache.json")
cache = {}
if os.path.exists(cache_file):
    with open(cache_file) as f:
        cache = json.load(f)

project_name = cache.get(pfd_filename)
if project_name:
    existing = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
    if project_name not in existing: project_name = None

if not project_name:
    projects_before = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
    imp = user.CreateObject('CompfdImport', 'ImportPfd')
    imp.SetAttribute("e:g_file", pfd_path)
    imp.g_target = user
    imp.Execute()
    imp.Delete()
    projects_after = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
    new_projects = list(projects_after - projects_before)
    if new_projects:
        project_name = new_projects[0]
        cache[pfd_filename] = project_name
        with open(cache_file, "w") as f:
            json.dump(cache, f, indent=2)
    else:
        raise RuntimeError(f"Import failed for {pfd_filename}")

proj = None
for p in (user.GetContents("*.IntPrj") or []):
    if p.loc_name == project_name:
        proj = p
        break
proj.Activate()
t_load_end = time.time()

# --- Activation ---
t_act_start = time.time()
study_case = None
for sc in proj.GetContents("*.IntCase", 1):
    if "Base SEN" in sc.loc_name:
        study_case = sc
        break
if study_case:
    study_case.Activate()

scenario = None
for scn in proj.GetContents("*.IntScenario", 1):
    if "Penetracion ERNC CC" in scn.loc_name:
        scenario = scn
        break
if scenario:
    scenario.Activate()
t_act_end = time.time()

# --- Load Flow ---
t_pf_start = time.time()
ldf = app.GetFromStudyCase("ComLdf")
if ldf:
    if ldf.HasAttribute("iopt_pbal"): ldf.SetAttribute("iopt_pbal", 4)
    if ldf.HasAttribute("iopt_init"): ldf.SetAttribute("iopt_init", 1)
    if ldf.HasAttribute("iopt_errlf"): ldf.SetAttribute("iopt_errlf", 1)
    err = ldf.Execute()
else:
    err = -1
t_pf_end = time.time()

pf_messages = []
out_window = app.GetOutputWindow()
if out_window:
    try:
        msgs = out_window.GetContent()
        if msgs:
            pf_messages = [str(m) for m in msgs[-30:]]
    except:
        pass

# --- Extraction ---
t_ext_start = time.time()

# 1. Transformers
trafos_list = []
for t in app.GetCalcRelevantObjects("*.ElmTr2"):
    trafos_list.append({
        "loc_name": t.loc_name,
        "loading_pct": round(float(safe_get(t, "c:loading", 0.0) or 0), 2),
        "p_hv_mw": round(float(safe_get(t, "m:P:bushv", 0.0) or 0), 2),
        "q_hv_mvar": round(float(safe_get(t, "m:Q:bushv", 0.0) or 0), 2),
        "bus_hv": safe_get(t, "bushv", "Unknown"),
        "bus_lv": safe_get(t, "buslv", "Unknown"),
        "zona": "N/A"
    })

trafos_res = {
    "escenario": "Penetracion ERNC CC",
    "error_code": err,
    "count": len(trafos_list),
    "transformadores": trafos_list
}

# 2. Generation by Zone
zone_data = {}
for config in ZONE_CONFIG.values():
    z_name = config['name']
    if z_name not in zone_data:
        zone_data[z_name] = {
            "zone": z_name, "lat": config['lat'], "lng": config['lng'],
            "gen_mw": 0.0, "solar": 0.0, "termica": 0.0, "eolica": 0.0, "hidro": 0.0, "bess": 0.0
        }

def classify_tech(name):
    if name.startswith("PFV"): return "solar"
    if name.startswith("TER"): return "termica"
    if name.startswith("PE"): return "eolica"
    if name.startswith("HE") or name.startswith("HP"): return "hidro"
    if name.startswith("BESS"): return "bess"
    return "termica"

for g_cls in ["*.ElmSym", "*.ElmGenstat"]:
    for g in app.GetCalcRelevantObjects(g_cls):
        if g.outserv == 1: continue
        p = float(safe_get(g, "m:P:bus1", 0.0) or 0)
        z_name = find_zone(g)
        tech = classify_tech(g.loc_name)
        if z_name in zone_data:
            zone_data[z_name]["gen_mw"] += p
            zone_data[z_name][tech] += p

gen_res = {
    "scenario": "Penetracion ERNC CC",
    "zones": list(zone_data.values())
}

# Round generation results
for z in gen_res["zones"]:
    for k in ["gen_mw", "solar", "termica", "eolica", "hidro", "bess"]:
        z[k] = round(z[k], 2)

# Write files
with open(os.path.join(RESULTS_DIR, "transformadores_ernc_cc.json"), "w") as f:
    json.dump(trafos_res, f, indent=2)

with open(os.path.join(RESULTS_DIR, "generacion_por_zona_ernc_cc.json"), "w") as f:
    json.dump(gen_res, f, indent=2)

print(f"Task completed. Error code: {err}")
```
