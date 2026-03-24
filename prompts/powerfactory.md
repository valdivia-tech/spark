# PowerFactory API Reference

Use these patterns when writing scripts for DIgSILENT PowerFactory.

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
    app = powerfactory.GetApplicationExt(None, None, '/min /nologo')
```

## Load a .pfd project

```python
user = app.GetCurrentUser()
projects_before = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}

import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
import_obj.SetAttribute("e:g_file", str(pfd_path))
import_obj.g_target = user
result = import_obj.Execute()  # 0 = success
import_obj.Delete()

projects_after = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
new_projects = projects_after - projects_before
project_name = list(new_projects)[0]
app.ActivateProject(project_name)
```

## Power flow

```python
study_case = app.GetActiveStudyCase()
if study_case is None:
    study_cases = app.GetActiveProject().GetContents("*.IntCase", 1)
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

```python
study_case = app.GetActiveStudyCase()
evt_shc = study_case.CreateObject('EvtShc', 'TempFault')

# Fault type: 0=three-phase, 1=two-phase, 2=two-phase-ground, 3=single-phase-ground
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
# Standard: 0=IEC60909, 1=Complete, 2=ANSI, 3=IEC61363
shc.iopt_mde = 0
error_code = shc.Execute()

ik_initial = evt_shc.GetAttribute("m:Ikss") if evt_shc.HasAttribute("m:Ikss") else 0
ip_peak = evt_shc.GetAttribute("m:ip") if evt_shc.HasAttribute("m:ip") else 0

# Bus voltages during fault
for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
    v_pu = bus.GetAttribute("m:u")
    v_drop = (1.0 - v_pu) * 100

# ALWAYS clean up temporary fault event
evt_shc.Delete()
```

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
