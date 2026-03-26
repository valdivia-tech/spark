# PowerFactory API Reference

Use these patterns when writing scripts for DIgSILENT PowerFactory.

IMPORTANT: Each script runs as a separate process. Nothing persists between scripts.
Every script that needs PowerFactory MUST do initialization + project loading from scratch.

## Initialization

```python
import sys, os

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
```

NOTE: Do NOT pass '/min /nologo' to GetApplicationExt — PowerFactory 2026 does not support those flags.

## Load a .pfd project

IMPORTANT: Projects persist in PowerFactory between runs. Re-importing creates duplicates
with "(N)" suffixes. ALWAYS use the cache pattern below to avoid this.

The .pfd filename does NOT match the internal project name (e.g., "7-bus.pfd" → "Taller 2").
Use a JSON cache file to remember the mapping after first import.

```python
import os, json

user = app.GetCurrentUser()
pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
pfd_filename = os.path.basename(pfd_path)

# Cache file maps pfd filenames to internal project names
cache_file = os.path.join("results", ".project_cache.json")
os.makedirs("results", exist_ok=True)
cache = {}
if os.path.exists(cache_file):
    with open(cache_file) as f:
        cache = json.load(f)

project_name = cache.get(pfd_filename)

if project_name:
    # Verify the cached project still exists
    existing = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
    if project_name not in existing:
        project_name = None  # cache stale, re-import

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

# Activate using the object
proj = None
for p in (user.GetContents("*.IntPrj") or []):
    if p.loc_name == project_name:
        proj = p
        break
proj.Activate()
```

## Power flow

NOTE: Study cases may be nested inside IntFolder objects. Use recursive search with GetContents("*.IntCase", 1)
where the second argument 1 means recursive search.

```python
study_case = app.GetActiveStudyCase()
if study_case is None:
    study_cases = app.GetActiveProject().GetContents("*.IntCase", 1)  # 1 = recursive
    if study_cases:
        study_cases[0].Activate()

ldf = app.GetFromStudyCase("ComLdf")
ldf.iopt_net = 0      # AC load flow
ldf.iopt_at = 1       # Automatic tap adjustment
ldf.iopt_asht = 1     # Automatic shunt adjustment
ldf.iopt_sim = 0      # Balanced, positive sequence
ldf.iopt_lim = 1      # Reactive power limits
error_code = ldf.Execute()  # 0=ok, 1=did not converge

# Bus voltages
for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
    if bus.HasAttribute("m:u"):
        v_pu = bus.GetAttribute("m:u")      # voltage p.u.
        v_kv = bus.GetAttribute("m:U")      # voltage kV
        angle = bus.GetAttribute("m:phiu")  # angle degrees

# Line loading
for line in app.GetCalcRelevantObjects("*.ElmLne"):
    if line.HasAttribute("c:loading"):
        loading = line.GetAttribute("c:loading")   # loading %
        current = line.GetAttribute("m:I:bus1")     # current kA
        p_mw = line.GetAttribute("m:P:bus1")        # active power MW
        q_mvar = line.GetAttribute("m:Q:bus1")      # reactive power Mvar

# Transformer loading
for t in app.GetCalcRelevantObjects("*.ElmTr2"):
    if t.HasAttribute("c:loading"):
        loading = t.GetAttribute("c:loading")
        i_hv = t.GetAttribute("m:I:bushv")   # HV side current kA
        i_lv = t.GetAttribute("m:I:buslv")   # LV side current kA

# Generators
for g in app.GetCalcRelevantObjects("*.ElmSym"):
    if g.HasAttribute("m:P:bus1"):
        p_mw = g.GetAttribute("m:P:bus1")
        q_mvar = g.GetAttribute("m:Q:bus1")
```

## Short circuit

IMPORTANT: Short circuit in PowerFactory has TWO approaches:
- **Method A (simple)**: Direct fault on a bus using ComShc only — no event needed
- **Method B (event-based)**: Create EvtShc for faults on lines at specific locations

### Method A: Short circuit on a bus (preferred for bus faults)

```python
# Find the target bus
target_bus = None
for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
    if "bus_name" in bus.loc_name:  # partial match
        target_bus = bus
        break

shc = app.GetFromStudyCase('ComShc')
# IMPORTANT: The attribute is iopt_mde, NOT iopt_shc
shc.iopt_mde = 0      # Standard: 0=IEC60909, 1=Complete, 2=ANSI, 3=IEC61363
shc.shcobj = target_bus  # set the fault location to the bus
shc.iopt_allbus = 0    # 0=single fault location, 2=all buses
# Fault type on ComShc: iopt_shc attribute
# 0=3-phase, 1=2-phase, 2=1-phase-ground, 3=2-phase-ground
shc.iopt_shc = "3PSC"  # IMPORTANT: Use STRING values: "3PSC", "2PSC", "1PSC", "2PSCG"
error_code = shc.Execute()  # 0 = ok

# Read results FROM THE BUS after calculation
if error_code == 0 and target_bus.HasAttribute("m:Ikss"):
    ikss = target_bus.GetAttribute("m:Ikss")   # Initial symmetrical SC current kA
    ip = target_bus.GetAttribute("m:ip")       # Peak SC current kA
    ib = target_bus.GetAttribute("m:Ib")       # Breaking current kA (if available)
    ik = target_bus.GetAttribute("m:Ik")       # Steady-state SC current kA (if available)
    skss = target_bus.GetAttribute("m:Skss")   # SC power MVA
```

IMPORTANT: Results are read from the BUS object (target_bus), NOT from the ComShc command object.
If Ikss returns 0, the fault location was not set correctly.

### Method B: Short circuit on a line (event-based)

```python
study_case = app.GetActiveStudyCase()
evt_shc = study_case.CreateObject('EvtShc', 'TempFault')

# Fault type on event: 0=three-phase, 1=two-phase, 2=two-phase-ground, 3=single-phase-ground
evt_shc.i_shc = 0

# Fault location on a line
line = None
for l in app.GetCalcRelevantObjects("*.ElmLne"):
    if l.loc_name == "line_name":
        line = l
        break
evt_shc.p_target = line
evt_shc.i_p_target = 50   # percentage along line (0-100)
evt_shc.R_f = 0.0          # fault resistance ohms

shc = app.GetFromStudyCase('ComShc')
shc.iopt_mde = 0   # IEC60909
error_code = shc.Execute()

# Read results from BUSES, not from the event
for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
    if bus.HasAttribute("m:Ikss"):
        ikss = bus.GetAttribute("m:Ikss")
        print(f"{bus.loc_name}: Ikss={ikss:.3f} kA")

# ALWAYS clean up temporary fault event
evt_shc.Delete()
```

### Common mistakes with short circuit
- Do NOT use `shc.iopt_shc = 0` (integer) — use `shc.iopt_shc = "3PSC"` (string)
- Do NOT read Ikss from the event object — read from bus objects
- Do NOT use `GetAttributes()` — it doesn't exist. Use `GetAttribute("attr_name")` for specific attributes
- Always check `HasAttribute()` before `GetAttribute()` to avoid crashes

## Element control

```python
# Activate/deactivate (outserv: 0=in service, 1=out of service)
element.outserv = 1  # take out of service
element.outserv = 0  # put in service

# Generator dispatch
gen.SetAttribute("pgini", 50.0)    # active power MW
gen.SetAttribute("qgini", 10.0)    # reactive power Mvar
gen.SetAttribute("usetp", 1.02)    # voltage setpoint p.u.

# Load
load.SetAttribute("plini", 20.0)   # active power MW
load.SetAttribute("qlini", 5.0)    # reactive power Mvar
load.SetAttribute("scale0", 0.8)   # scaling factor

# Transformer tap
trafo.SetAttribute("nntap", 5)     # tap position

# Line parameters
line.GetAttribute("dline")         # length km
line.GetAttribute("Inom")          # nominal current kA
```

## Safe attribute access

```python
def safe_get(obj, attr, default=None):
    try:
        if obj.HasAttribute(attr):
            val = obj.GetAttribute(attr)
            return val if val is not None else default
    except Exception:
        pass
    return default
```

## Element type patterns

| Type | Pattern |
|------|---------|
| Buses/Terminals | `*.ElmTerm` |
| Lines | `*.ElmLne` |
| 2-winding Transformers | `*.ElmTr2` |
| Synchronous generators | `*.ElmSym` |
| Static generators | `*.ElmGenstat` |
| Loads | `*.ElmLod` |
| External grids | `*.ElmXnet` |
| Study cases | `*.IntCase` |

## Important rules

1. Always use try/finally to clean up fault events (evt_shc.Delete())
2. Check HasAttribute before GetAttribute — not all elements have all attributes after a calculation
3. outserv=0 means IN service (inverted logic, careful)
4. If power flow doesn't converge, report error_code and suggest adjustments
5. Don't modify the original .pfd — work on the imported copy

## Base adjustment procedure (when power flow doesn't converge)

When adding new projects and power flow fails to converge:

1. Read error_code, find the bus with highest mismatch
2. If active mismatch (MW): adjust generator dispatch, check slack
3. If reactive mismatch (MVAr): adjust taps, reactive compensation
4. If voltage issues: adjust generator voltage setpoints
5. Retry power flow. Maximum 10 attempts.

```python
# Scale generation proportionally
factor = 0.9  # reduce 10%
for gen in app.GetCalcRelevantObjects("*.ElmSym"):
    if gen.outserv == 0:  # only active ones
        p_actual = gen.GetAttribute("pgini")
        gen.SetAttribute("pgini", p_actual * factor)
```
