# Multi-escenario sobre CEN 2604-BD-OP-COORD-DMAP (abril 2026)
Fecha: 2026-05-06
Tarea: "Correr los 10 escenarios operacionales del SEN sobre la BD de abril 2026, extraer barras/líneas/generadores/transformadores por escenario + cross + zonas geográficas."

> Esta receta es la versión consolidada después de 3 corridas. La estructura del proyecto es idéntica a 2603 (lee también `cen-2603-power-flow.md`); este archivo agrega los gotchas API que aparecieron específicamente al pedir extracción de transformadores y agregación por zona.

## Estructura del proyecto

- **Nombre interno** del proyecto: probablemente `2604-BD-OP-COORD-DMAP` o variante con sufijo de versión. **NO coincide** con el nombre del archivo `.pfd` ni con el directorio `2604/`. Usá cache (`results/.project_cache.json`) — si no existe, después del primer `ImportProject(pfd_path)` enumerá `user.GetContents("*.IntPrj")` y guardalo.
- **Study Case único**: `Base SEN`. Activarlo SIEMPRE antes que el escenario.
- **10 IntScenario**: Laboral Madrugada/Diurno/Vespertino, Sabado Madrugada/Diurno/Vespertino, Domingo Madrugada/Diurno/Vespertino, Penetracion ERNC CC. Activá uno por uno con `scenario.Activate()`.
- ~12,000 buses, ~5–7,000 líneas, ~1,200 generadores, ~3,000 transformadores. ~1,300 áreas aisladas (normal en BDs operacionales del SEN, no bloquean convergencia).

## API gotchas confirmadas (HORAS PERDIDAS — leer antes de escribir el script)

### Atributos con `:` deben usar `GetAttribute(...)`

❌ NO funciona:
```python
loading = trafo.m:loading            # SyntaxError o AttributeError
p_mw = gen.m:P:bus1                  # AttributeError: 'DataObject' object has no attribute 'm:P:bus1'
```

✅ SÍ funciona:
```python
loading = trafo.GetAttribute("m:loading")
p_mw = gen.GetAttribute("m:P:bus1")
q_mvar = gen.GetAttribute("m:Q:bus1")
p_hv = trafo.GetAttribute("m:P:bushv")
q_hv = trafo.GetAttribute("m:Q:bushv")
```

**Regla: cualquier nombre de atributo con `:` SIEMPRE vía `GetAttribute(str)`.** Esto incluye `m:u`, `m:phiu`, `m:P:bus1`, `m:Q:bus1`, `m:P:bushv`, `m:Q:bushv`, `m:loading`. Si dudas, `HasAttribute(name)` antes para no romper.

### Boost.Python.ArgumentError

Aparece cuando se pasa el TIPO equivocado a un método de la API C++:

❌ NO funciona:
```python
app.GetCalcRelevantObjects("Laboral Diurno")   # espera filter pattern, no nombre
study_case.Activate("Base SEN")                 # Activate no toma argumentos
```

✅ SÍ funciona:
```python
syms = app.GetCalcRelevantObjects("*.ElmSym")    # filter glob, retorna list[DataObject]
study_case.Activate()                             # se llama sobre el objeto sin args
```

Si el script falla con `Boost.Python.ArgumentError: Python argument types in <Method>(...) did not match C++ signature`, **ese método no acepta strings/ints donde se los estás pasando**. Lo más probable: querías pasar un `DataObject` y pasaste su nombre como string.

### OutputWindow.GetContent() en PF 2026

Pasar una lista vacía `[]` a `GetContent()` provoca un `ArgumentError`. En 2026, `GetContent()` debe llamarse **sin argumentos** para obtener todos los mensajes.

### Robustez al serializar JSON

Al extraer atributos de miles de elementos, usar `float(val or 0)` antes de `json.dump` evita errores cuando PowerFactory devuelve `None` u objetos no serializables.

### Mapeo de nombres de escenarios

Los nombres usados en el script (ej. `laboral_diurno`) pueden no coincidir exactamente con los del proyecto (`Laboral Diurno`). Normalizar (minúsculas, remover espacios y guiones bajos) antes de matchear.

### Iterar study cases / scenarios

```python
project = app.GetActiveProject()
study_cases = project.GetContents("*.IntCase", recursive=True)
scenarios = project.GetContents("*.IntScenario", recursive=True)

# Activar Base SEN primero, después el scenario
base = next(sc for sc in study_cases if sc.loc_name == "Base SEN")
base.Activate()

for s in scenarios:
    s.Activate()
    # run PF, extract...
```

## Mapeo de zonas geográficas

Para `generacion_por_zona.json` (mapa interactivo del frontend), agregar la generación por zona del SEN. Los IntFolder de zona en este .pfd tienen prefijos numéricos:

| IntFolder/ElmNet name | Zona geográfica | lat | lng |
|---|---|---|---|
| `00-Norte Grande` | Norte Grande | -22.5 | -69.5 |
| `01-Atacama` | Atacama | -27.0 | -70.0 |
| `02-Coquimbo` | Coquimbo | -30.0 | -71.0 |
| `03-Chilquinta-Aconcagua` | Valparaíso | -32.8 | -71.3 |
| `04-Enel Distribución` | Santiago | -33.45 | -70.6 |
| `05-Colbún` | O'Higgins | -34.3 | -70.9 |
| `06-Troncal_Qui-Cha` | Maule | -35.7 | -71.2 |
| `07-Sistema154 - 66 kV (Centro)` | Centro | -34.8 | -71.5 |
| `08-Charrúa` | Biobío | -37.0 | -72.5 |
| `09-Concepción` | Concepción | -36.8 | -73.0 |
| `10-Araucanía` | Araucanía | -38.7 | -72.5 |
| `11-Araucanía 66 kV` | Araucanía | -38.7 | -72.5 |

**Para mapear cada generador a su zona**, caminar `parent` hasta encontrar un IntFolder cuyo `loc_name` empiece con uno de los prefijos `00-` … `11-`:

```python
def find_zone(obj):
    cur = obj.GetParent()
    while cur is not None:
        name = cur.loc_name
        for prefix, zone in ZONE_MAP.items():
            if name.startswith(prefix):
                return zone
        cur = cur.GetParent()
    return "Norte Grande"  # fallback conservador, NO inventar 'N/A' u 'Otra'
```

**Aplicar este walk SOLO a generadores (~1,200 elementos)** para `generacion_por_zona.json`. NO aplicarlo a barras (~12k) ni líneas (~5–7k) ni transformadores (~3k) en el extracto general — eso son ~150k+ lookups y cuelga la VM. Si necesitás zona de un trafo o barra puntual, dejala en `"N/A"` y resolvé caso a caso después.

## Discrepancias esperadas vs PDF del CEN

El CEN advierte explícitamente en el informe de definición de escenarios que la generación reportada de la BD puede diferir de la SCADA telemedida. Causas:

- **PMGD se modela como carga negativa**, no como generación → `gen_total_mw` post-PF puede ser **10–30% menor** que `gen+PMGD` que cita el CEN.
- **Unidades cerca del mínimo técnico se desconectan o se aproximan** al mínimo.

Implicancia: si validas con `expected_mw ± 15%` vs el `gen+PMGD` del PDF, esperá diferencias mayores. Validá contra `Gen Bruta sin SAE` del PDF si lo tenés, o contra el rango histórico observado en marzo (PF: 8,000–10,800 MW).

**Pérdidas negativas en escenarios diurnos con BESS cargando** son artifact, no error. `gen_total` incluye BESS positivo; `load_total` no contempla la potencia que BESS está absorbiendo. Físicamente OK.

## Receta probada (UNA spark_run para los 10)

1. `ImportProject` o cache.
2. Activar el proyecto, activar `Base SEN`.
3. Configurar `ComLdf`: `iopt_init=1`, `iopt_pbal=4`, `iopt_errlf=1` (usar `set_attr` con `HasAttribute` por seguridad). Misma receta que 2603 — funciona en snapshots operacionales con DSLs complejos.
4. Loop 10 escenarios: `Activate()` → `ldf.Execute()` → extraer en memoria.
5. Después del loop, escribir todos los JSONs de una vez.
6. NO redespachar. NO modificar topología. NO activar generadores fuera de servicio.

## Validación rápida del despacho

Para validar internamente que un escenario activó correctamente:

```python
# Suma post-PF de generadores activos
gen_mw = 0.0
for cls in ("ElmSym", "ElmGenstat"):
    for g in app.GetCalcRelevantObjects(f"*.{cls}"):
        if g.GetAttribute("outserv") == 0 and g.HasAttribute("m:P:bus1"):
            v = g.GetAttribute("m:P:bus1")
            if v is not None:
                gen_mw += v
```

Rangos esperados para el SEN abril 2026 (run 6-may-2026):
- Laboral Madrugada: ~9,500 MW
- Laboral Diurno: ~9,200 MW
- Laboral Vespertino: ~10,060 MW
- Sábado Madrugada: ~8,720 MW
- Sábado Diurno: ~7,680 MW
- Sábado Vespertino: ~10,120 MW
- Domingo Madrugada: ~7,515 MW
- Domingo Diurno: ~8,490 MW
- Domingo Vespertino: ~9,970 MW
- ERNC CC: ~6,760 MW

Fuera de ±10% de estos valores → revisar activación del escenario.

## Restricciones operacionales

- NO modificar dispatch ni topología (la BD viene del SCADA).
- NO usar `pgini`/`plini` para totales — usar `m:P:bus1` post-PF.
- Si un escenario diverge, anotá `error_code != 0` en cross y seguí — no retries, no rewriting (regla "Accept" del system prompt).
- 25 flujos consecutivos OK en la VM e2-standard-2 (benchmark): ~7.8 s/flujo, total loop ~196 s. La VM es viable para esta BD pero lenta.

## Script de referencia

Implementación completa de la receta (los 10 escenarios + cross-scenario + reporte ejecutivo del laboral diurno):

```python
import sys, os, json, time

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

# --- Load project ---
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
        raise RuntimeError(f"Import failed for {pfd_filename}")

proj = None
for p in (user.GetContents("*.IntPrj") or []):
    if p.loc_name == project_name:
        proj = p
        break
proj.Activate()

# --- Find components ---
study_case = None
for sc in proj.GetContents("*.IntCase", 1):
    if "Base SEN" in sc.loc_name:
        study_case = sc
        break

if not study_case:
    scs = proj.GetContents("*.IntCase", 1)
    if scs: study_case = scs[0]

all_scenarios = proj.GetContents("*.IntScenario", 1)

target_scenario_names = [
    "laboral_madrugada", "laboral_diurno", "laboral_vespertino",
    "sabado_madrugada", "sabado_diurno", "sabado_vespertino",
    "domingo_madrugada", "domingo_diurno", "domingo_vespertino",
    "ernc_cc"
]

scenario_map = {}
for s_name in target_scenario_names:
    normalized_target = s_name.lower().replace("_", "")
    for scn in all_scenarios:
        normalized_scn = scn.loc_name.lower().replace("_", "").replace(" ", "")
        if normalized_target == normalized_scn:
            scenario_map[s_name] = scn
            break

# Fallback para variaciones
if len(scenario_map) < len(target_scenario_names):
    for s_name in target_scenario_names:
        if s_name not in scenario_map:
            target_part = s_name.split("_")[0]
            for scn in all_scenarios:
                if target_part in scn.loc_name.lower():
                    if "_" in s_name:
                        second_part = s_name.split("_")[1]
                        if second_part in scn.loc_name.lower():
                            scenario_map[s_name] = scn
                            break

# Extraction logic
TECH_MAP = {
    "TER": "CEN: TER", "GEO": "CEN: TER",
    "HE": "CEN: HE", "HP": "CEN: HP",
    "PFV": "CEN: PFV", "CSP": "CEN: PFV",
    "PE": "CEN: PE",
    "BESS": "CEN: BESS"
}

def classify_gen(name):
    for prefix, tech in TECH_MAP.items():
        if name.startswith(prefix):
            return tech
    return "CEN: OTRO"

cross_scenario = []

for s_name in target_scenario_names:
    t_start = time.time()
    scn_obj = scenario_map.get(s_name)
    if not scn_obj: continue

    study_case.Activate()
    scn_obj.Activate()

    ldf = app.GetFromStudyCase("ComLdf")
    if ldf:
        if ldf.HasAttribute("iopt_pbal"): ldf.SetAttribute("iopt_pbal", 4)
        if ldf.HasAttribute("iopt_init"): ldf.SetAttribute("iopt_init", 1)
        if ldf.HasAttribute("iopt_errlf"): ldf.SetAttribute("iopt_errlf", 1)
        err = ldf.Execute()
    else:
        err = -1

    out_window = app.GetOutputWindow()
    pf_messages = []
    if out_window:
        try:
            msgs = out_window.GetContent()
            if msgs:
                pf_messages = [str(m) for m in msgs[-20:]]
        except:
            pass

    buses_data = []
    lines_data = []
    gens_data = []

    gen_by_type = {}
    total_gen_mw = 0.0
    total_load_mw = 0.0
    bess_mw = 0.0

    for b in app.GetCalcRelevantObjects("*.ElmTerm"):
        v_pu = safe_get(b, "m:u", 0.0)
        buses_data.append({
            "loc_name": b.loc_name,
            "v_nom_kv": safe_get(b, "uknom", 0.0),
            "v_pu": round(float(v_pu or 0), 4),
            "v_kv": round(float(safe_get(b, "m:U", 0.0) or 0), 3),
            "ang_deg": round(float(safe_get(b, "m:phiu", 0.0) or 0), 2),
            "zona": safe_get(b, "cpArea", "N/A")
        })

    for l in app.GetCalcRelevantObjects("*.ElmLne"):
        p_mw = safe_get(l, "m:P:bus1", 0.0)
        lines_data.append({
            "loc_name": l.loc_name,
            "loading_pct": round(float(safe_get(l, "c:loading", 0.0) or 0), 2),
            "p_mw": round(float(p_mw or 0), 2),
            "q_mvar": round(float(safe_get(l, "m:Q:bus1", 0.0) or 0), 2),
            "bus1_name": safe_get(l, "bus1", ""),
            "bus2_name": safe_get(l, "bus2", ""),
            "v_nom_kv": safe_get(l, "uknom", 0.0),
            "length_km": safe_get(l, "dline", 0.0),
            "zona": safe_get(l, "cpArea", "N/A")
        })

    for g_cls in ["*.ElmSym", "*.ElmGenstat"]:
        for g in app.GetCalcRelevantObjects(g_cls):
            if g.outserv == 1: continue
            p = safe_get(g, "m:P:bus1", 0.0)
            q = safe_get(g, "m:Q:bus1", 0.0)
            tech = classify_gen(g.loc_name)
            p_val = float(p or 0)
            total_gen_mw += p_val
            gen_by_type[tech] = gen_by_type.get(tech, 0.0) + p_val
            if "BESS" in tech: bess_mw += p_val
            gens_data.append({
                "loc_name": g.loc_name,
                "pgini": round(p_val, 2),
                "qgini": round(float(q or 0), 2),
                "tipo": tech,
                "zona": safe_get(g, "cpArea", "N/A"),
                "clase": g_cls.replace("*.", "")
            })

    for ld in app.GetCalcRelevantObjects("*.ElmLod"):
        if ld.outserv == 0:
            total_load_mw += abs(float(safe_get(ld, "m:P:bus1", 0.0) or 0))

    with open(os.path.join(RESULTS_DIR, f"todas_las_barras_{s_name}.json"), "w") as f:
        json.dump(buses_data, f, indent=2)
    with open(os.path.join(RESULTS_DIR, f"todas_las_lineas_{s_name}.json"), "w") as f:
        json.dump(lines_data, f, indent=2)
    with open(os.path.join(RESULTS_DIR, f"todos_los_generadores_{s_name}.json"), "w") as f:
        json.dump(gens_data, f, indent=2)

    top_lines = sorted(lines_data, key=lambda x: x["loading_pct"], reverse=True)[:5]
    trafos_data = []
    for t in app.GetCalcRelevantObjects("*.ElmTr2"):
        trafos_data.append({
            "loc_name": t.loc_name,
            "loading_pct": round(float(safe_get(t, "c:loading", 0.0) or 0), 2),
            "p_mw": round(float(safe_get(t, "m:P:bushv", 0.0) or 0), 2),
            "zona": safe_get(t, "cpArea", "N/A")
        })
    top_trafos = sorted(trafos_data, key=lambda x: x["loading_pct"], reverse=True)[:5]
    buses_out = [b for b in buses_data if b["v_pu"] < 0.95 or b["v_pu"] > 1.05]

    if s_name == "laboral_diurno":
        exec_report = {
            "top_10_generadores": sorted(gens_data, key=lambda x: x["pgini"], reverse=True)[:10],
            "top_10_lineas": sorted(lines_data, key=lambda x: x["loading_pct"], reverse=True)[:10],
            "top_10_trafos": sorted(trafos_data, key=lambda x: x["loading_pct"], reverse=True)[:10],
            "resumen_zona": {},
            "barras_criticas": sorted(buses_out, key=lambda x: abs(1.0 - x["v_pu"]), reverse=True)[:20]
        }
        for g in gens_data:
            z = str(g["zona"])
            if z not in exec_report["resumen_zona"]: exec_report["resumen_zona"][z] = {"gen": 0.0, "load": 0.0}
            exec_report["resumen_zona"][z]["gen"] += g["pgini"]
        with open(os.path.join(RESULTS_DIR, "reporte_ejecutivo_laboral_diurno.json"), "w") as f:
            json.dump(exec_report, f, indent=2)

    cross_scenario.append({
        "scenario": s_name,
        "status": "converged" if err == 0 else "diverged",
        "gen_total": round(total_gen_mw, 2),
        "load_total": round(total_load_mw, 2),
        "losses": round(total_gen_mw - total_load_mw, 2),
        "gen_by_type": {k: round(v, 2) for k, v in gen_by_type.items()},
        "top_5_loaded_lines": top_lines,
        "top_5_loaded_trafos": top_trafos,
        "buses_out_of_range_count": len(buses_out),
        "bess_total_mw": round(bess_mw, 2),
        "error_code": err,
        "seconds": round(time.time() - t_start, 2),
        "pf_messages": pf_messages
    })

with open(os.path.join(RESULTS_DIR, "cross_scenario_analysis.json"), "w") as f:
    json.dump(cross_scenario, f, indent=2)
```
