# Flujo de Potencia — CEN 2603-BD-OP-COORD-DMAP
Fecha: 2026-04-11
Tarea: "Correr flujo de potencia en base de datos operacional CEN 2603"

## Lecciones aprendidas (15+ intentos sintetizados)

- **Estructura del proyecto**: Study Case único `Base SEN` (IntCase) + escenarios separados (IntScenario). Los escenarios NO son study cases — activar por separado después de activar `Base SEN`.
- **Nombre interno**: `2305-BD-Ovalle.12072023` (NO coincide con el nombre del .pfd).
- **Método que funciona**: Slack distribuido (`iopt_pbal=4`) + flat start (`iopt_init=1`) + ignorar errores DSL (`iopt_errlf=1`). Validado en los 10 escenarios operacionales.
- **`set_attr` obligatorio**: Los atributos `iopt_pbal`, `iopt_init`, `iopt_errlf` pueden no existir en todas las versiones de PowerFactory. SIEMPRE usar la función `set_attr` que verifica con `HasAttribute`.
- **ElmDsl**: NO es necesario deshabilitarlos si se usa `iopt_errlf=1`. Mantenerlos activos preserva la configuración original.
- **SCADA dispatch intocable**: Los valores `pgini` vienen de snapshots SCADA reales. NO modificar despacho, NO activar/desactivar generadores, NO crear/modificar ElmXnet.
- **Áreas aisladas**: Se detectan ~1,200-1,300 áreas aisladas — es normal para snapshots operacionales del SEN, no impiden convergencia.
- **Clasificación de generadores**: Usar prefijos CEN del nombre del generador.

## Lo que NO funciona (probado y fallido)

- **Redespacho manual** (escalar pgini, duplicar despacho, dispatch de emergencia) — todos fallaron
- **Crear ElmXnet como slack** — la red ya tiene su configuración de referencia
- **Activar generadores fuera de servicio** — el escenario define qué está activo
- **No usar iopt_errlf=1** con ElmDsl activos — causa errores de inicialización y genera ~4,700 MW (incorrecto)
- **Apply() en vez de Activate()** para escenarios — Activate() es el método correcto
- **Flujo DC** — también falló
- **Asignar slack manual** — no necesario con iopt_pbal=4

## Script base

```python
import sys, os, json, time

t0 = time.time()

# --- PowerFactory init ---
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)
pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')
import powerfactory
app = powerfactory.GetApplicationExt(None, None)

RESULTS_DIR = os.environ.get("SPARK_RESULTS_DIR", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# --- Load project (cache) ---
user = app.GetCurrentUser()
pfd_path = os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd"))
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

t_load = time.time() - t0

# --- Activate study case + scenario ---
SCENARIO = "Laboral Diurno"  # <-- CAMBIAR SEGÚN ESCENARIO

t1 = time.time()
for sc in proj.GetContents("*.IntCase", 1):
    if "Base SEN" in sc.loc_name:
        sc.Activate()
        break

for scn in app.GetCalcRelevantObjects("*.IntScenario"):
    if SCENARIO in scn.loc_name:
        scn.Activate()
        break

t_activate = time.time() - t1

# --- Configure solver ---
ldf = app.GetFromStudyCase("ComLdf")

def set_attr(obj, attr, val):
    if obj.HasAttribute(attr):
        try:
            obj.SetAttribute(attr, val)
        except:
            setattr(obj, attr, val)

set_attr(ldf, "iopt_pbal", 4)   # distributed slack
set_attr(ldf, "iopt_init", 1)   # flat start
set_attr(ldf, "iopt_errlf", 1)  # CRITICAL: ignore DSL/DLL errors

# --- Run power flow ---
t2 = time.time()
error_code = ldf.Execute()
t_pf = time.time() - t2

# --- Capture PF messages ---
out_window = app.GetOutputWindow()
pf_messages = []
if out_window:
    msgs = out_window.GetContent([])
    if msgs and len(msgs) > 1:
        pf_messages = [str(m) for m in msgs[1][-20:]]

# --- Extract results ---
t3 = time.time()

# Generator classification by CEN prefix
TECH_MAP = {
    "TER": "Termica", "GEO": "Termica",
    "HE": "Hidraulica", "HP": "Hidraulica",
    "PFV": "Solar", "CSP": "Solar",
    "PE": "Eolica",
    "BESS": "Almacenamiento"
}

def classify_gen(name):
    for prefix, tech in TECH_MAP.items():
        if name.startswith(prefix):
            return tech
    return "Otro"

gen_by_tech = {}
total_gen = 0.0
for cls in ["*.ElmSym", "*.ElmGenstat"]:
    for g in app.GetCalcRelevantObjects(cls):
        if g.GetAttribute("outserv") == 0 and g.HasAttribute("m:P:bus1"):
            p = g.GetAttribute("m:P:bus1")
            if p is not None:
                total_gen += p
                tech = classify_gen(g.loc_name)
                gen_by_tech[tech] = gen_by_tech.get(tech, 0.0) + p

total_load = 0.0
for ld in app.GetCalcRelevantObjects("*.ElmLod"):
    if ld.GetAttribute("outserv") == 0 and ld.HasAttribute("m:P:bus1"):
        p = ld.GetAttribute("m:P:bus1")
        if p is not None:
            total_load += p

t_extract = time.time() - t3

results = {
    "status": "converged" if error_code == 0 else "diverged",
    "error_code": error_code,
    "scenario": SCENARIO,
    "gen_total_mw": round(total_gen, 2),
    "load_total_mw": round(total_load, 2),
    "losses_mw": round(total_gen - total_load, 2),
    "gen_by_tech_mw": {k: round(v, 2) for k, v in sorted(gen_by_tech.items())},
    "pf_messages": pf_messages,
    "timing": {
        "load_project_s": round(t_load, 2),
        "activate_s": round(t_activate, 2),
        "power_flow_s": round(t_pf, 2),
        "extract_s": round(t_extract, 2),
        "total_s": round(time.time() - t0, 2)
    }
}

with open(os.path.join(RESULTS_DIR, "power_flow.json"), "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"Status: {results['status']}")
print(f"Gen: {results['gen_total_mw']} MW | Load: {results['load_total_mw']} MW | Losses: {results['losses_mw']} MW")
```

## Clasificación de generadores por prefijo CEN

| Prefijo | Tecnología | Tipo PF | Cantidad |
|---------|-----------|---------|----------|
| TER | Térmica (carbón, gas, diésel) | ElmSym | 134 |
| HE | Hidroeléctrica (embalse) | ElmSym | 21 |
| HP | Hidroeléctrica (pasada) | ElmSym/ElmGenstat | 100 |
| PFV | Solar fotovoltaica | ElmGenstat | 165 |
| PE | Eólica | ElmGenstat | 138 |
| BESS | Almacenamiento (baterías) | ElmGenstat | 120 |
| CSP | Solar concentración | ElmGenstat | ~2 |
| GEO | Geotermia | ElmSym | ~1 |

## Valores de referencia — 10 escenarios validados

| Escenario | Gen (MW) | Carga (MW) | Pérdidas (MW) | CEN Ref (MW) | Delta |
|-----------|----------|------------|---------------|-------------|-------|
| Laboral Madrugada | 8,011 | 7,780 | 231 | 8,033 | -0.28% |
| Laboral Diurno | 9,320 | 8,892 | 428 | 9,388 | -0.73% |
| Laboral Vespertino | 10,844 | 10,509 | 413 | 10,924 | -0.73% |
| Sábado Madrugada | 8,560 | 8,322 | 237 | 8,568 | -0.1% |
| Sábado Diurno | 8,375 | 8,198 | 254 | 8,301 | +0.9% |
| Sábado Vespertino | 9,954 | 9,702 | 330 | ~10,034 | -0.8% |
| Domingo Madrugada | 8,115 | 7,937 | 178 | 8,116 | ~0% |
| Domingo Diurno | 8,691 | 8,566 | 126 | 8,771 | -0.9% |
| Domingo Vespertino | 9,774 | 9,545 | 313 | 9,880 | -1.1% |
| ERNC CC | 8,061 | 7,744 | 317 | 8,098 | -0.45% |

Si tu resultado de generación se desvía >5% de estos valores, algo está mal en la configuración.
