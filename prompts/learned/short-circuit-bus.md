# Cortocircuito trifásico en barra
Fecha: 2026-03-26
Tarea: "haz un cortocircuito trifásico en la barra S/E A 110 kV del proyecto 7-bus.pfd y muestra Ikss, ip y Skss"

## Lecciones aprendidas
- **Atributo `iopt_shc` como string.** Para definir el tipo de falla en el comando `ComShc`, se debe usar un valor de tipo string como `"3PSC"` (3-phase short circuit).
- **Lectura de resultados desde el objeto Terminal.** Los resultados del cálculo (`Ikss`, `ip`, `Skss`) no se leen del comando `ComShc`, sino directamente de los atributos del objeto terminal (`ElmTerm`) donde se aplicó la falla.
- **Uso de `shcobj` para definir la ubicación.** Para una falla en una barra específica, se asigna el objeto de la barra a `shc.shcobj` y se asegura que `shc.iopt_allbus = 0`.
- **Atributos comunes de cortocircuito:** `m:Ikss` (corriente inicial simétrica), `m:ip` (corriente pico) y `m:Skss` (potencia de cortocircuito inicial).

## Script
```python
import sys, os, json

# Initialization
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)
pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')
import powerfactory
app = powerfactory.GetApplicationExt(None, None)

# Load project (using cache pattern)
user = app.GetCurrentUser()
pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
pfd_filename = os.path.basename(pfd_path)
cache_file = os.path.join("results", ".project_cache.json")
os.makedirs("results", exist_ok=True)
with open(cache_file) as f:
    cache = json.load(f)
project_name = cache[pfd_filename]
proj = [p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name][0]
proj.Activate()

# Activate study case
study_cases = proj.GetContents("*.IntCase", 1)
study_cases[0].Activate()

# Find target bus
target_bus = [b for b in app.GetCalcRelevantObjects("*.ElmTerm") if "S/E A 110 kV" in b.loc_name][0]

# Configure and run short circuit (IEC 60909)
shc = app.GetFromStudyCase('ComShc')
shc.iopt_mde = 0       # 0=IEC 60909
shc.shcobj = target_bus
shc.iopt_allbus = 0    # single fault location
shc.iopt_shc = "3PSC"  # 3-phase short circuit
error_code = shc.Execute()

# Retrieve results
results = {
    "Ikss": target_bus.GetAttribute("m:Ikss"),
    "ip": target_bus.GetAttribute("m:ip"),
    "Skss": target_bus.GetAttribute("m:Skss")
}

with open("results/short_circuit.json", "w") as f:
    json.dump(results, f, indent=2)
```
