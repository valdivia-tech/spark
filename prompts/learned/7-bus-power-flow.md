# Flujo de Potencia — 7-bus.pfd (modelo didáctico)
Fecha: 2026-04-11
Tarea: "Importar 7-bus.pfd, correr flujo de potencia, extraer resultados"

## Lecciones aprendidas

- **Proyecto simple** — 9 barras, 5 líneas, ~14 MW. NO tiene Study Case (IntCase).
- **Nombre interno diferente al .pfd**: "7-bus.pfd" se importa como "Taller 2". SIEMPRE usar cache.
- **NO buscar Study Case** — no existe, causa error. Activar proyecto directamente.
- **NO modificar slack ni despacho** — ya configurado correctamente (ElmXnet o generador como Slack).
- **NO deshabilitar ElmDsl** — no hay modelos dinámicos.
- **NUNCA reimportar** si ya existe en PowerFactory — crea duplicados con sufijo "(N)".
- **Study cases anidados**: usar `GetContents("*.IntCase", 1)` con segundo argumento `1` para búsqueda recursiva.
- **`proj.Activate()`** con el objeto, no `app.ActivateProject()` con string.
- **Path relativo al workspace**: `../projects/7-bus.pfd`.

## Script

```python
import sys, os, json, time

t0 = time.time()

# 1. Initialize PowerFactory
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)
pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')
import powerfactory
app = powerfactory.GetApplicationExt(None, None)

RESULTS_DIR = os.environ.get("SPARK_RESULTS_DIR", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# 2. Load project using cache
user = app.GetCurrentUser()
pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
pfd_filename = os.path.basename(pfd_path)
cache_file = os.path.join(RESULTS_DIR, ".project_cache.json")
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
        raise RuntimeError(f"Import failed: no new project for {pfd_filename}")

proj = None
for p in (user.GetContents("*.IntPrj") or []):
    if p.loc_name == project_name:
        proj = p
        break
proj.Activate()

# 3. Activate study case (if exists) and run load flow
study_cases = proj.GetContents("*.IntCase", 1)
if study_cases:
    study_cases[0].Activate()

ldf = app.GetFromStudyCase("ComLdf")
ldf.iopt_net = 0
ldf.iopt_at = 1
ldf.iopt_asht = 1
ldf.iopt_sim = 0
ldf.iopt_lim = 1
error_code = ldf.Execute()

t_pf = time.time() - t0

# 4. Extract results
results = {"status": "converged" if error_code == 0 else "diverged", "error_code": error_code}
if error_code == 0:
    buses = {}
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        if bus.HasAttribute("m:u"):
            buses[bus.loc_name] = {
                "v_pu": round(bus.GetAttribute("m:u"), 4),
                "v_kv": round(bus.GetAttribute("m:U"), 2),
                "angle_deg": round(bus.GetAttribute("m:phiu"), 2)
            }
    results["buses"] = buses

with open(os.path.join(RESULTS_DIR, "voltages.json"), "w") as f:
    json.dump(results, f, indent=2)
```

## Valores de referencia

- Generación: ~14.10 MW
- Carga: 14.00 MW
- Pérdidas: ~0.10 MW
- Tensión min: ~0.978 p.u. (S/E C 13.8 kV)
- Carga max línea: ~31.1% (Tramo 2)
