# Importar proyecto y correr flujo de potencia
Fecha: 2026-03-24
Tarea: "carga projects/7-bus.pfd, corre un flujo de potencia y muestra las tensiones en todas las barras"

## Lecciones aprendidas

- **El nombre del proyecto NO es el nombre del archivo .pfd.** El archivo "7-bus.pfd" se importó como "Taller 2(177)". PowerFactory usa el nombre interno del proyecto, no el filename. Solución: comparar el set de proyectos antes y después del import para detectar el nombre real.
- **Los study cases pueden estar anidados en IntFolder.** Usar `GetContents("*.IntCase", 1)` con el segundo argumento `1` para búsqueda recursiva. Sin esto, no se encuentran.
- **Usar `proj.Activate()` con el objeto, no `app.ActivateProject()`.** Si ya tienes el objeto del proyecto (del loop de búsqueda), usa `.Activate()` directamente. `app.ActivateProject(name)` necesita el string exacto.
- **El path al .pfd es relativo al workspace, no al directorio del script.** Como el workspace es `./workspace/` y los proyectos están en `./projects/`, la ruta correcta desde el script es `../projects/7-bus.pfd`.
- **Verificar que `HasAttribute` antes de `GetAttribute`.** No todos los terminales tienen resultados de cálculo si el flujo no convergió. Siempre chequear con `bus.HasAttribute("m:u")` antes de leer.

## Script

```python
import sys, os, json

# 1. Initialize PowerFactory
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory
app = powerfactory.GetApplicationExt(None, None)

# 2. Import project using before/after set comparison
user = app.GetCurrentUser()
pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))

projects_before = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}

import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
import_obj.SetAttribute("e:g_file", pfd_path)
import_obj.g_target = user
import_obj.Execute()
import_obj.Delete()

projects_after = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
new_projects = list(projects_after - projects_before)

project_name = new_projects[0]
proj = None
for p in (user.GetContents("*.IntPrj") or []):
    if p.loc_name == project_name:
        proj = p
        break

proj.Activate()

# 3. Find study case (recursive) and run load flow
study_cases = proj.GetContents("*.IntCase", 1)
study_cases[0].Activate()

ldf = app.GetFromStudyCase("ComLdf")
ldf.iopt_net = 0
ldf.iopt_at = 1
ldf.iopt_asht = 1
ldf.iopt_sim = 0
ldf.iopt_lim = 1
error_code = ldf.Execute()

# 4. Extract bus voltages
results = {}
if error_code == 0:
    for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
        if bus.HasAttribute("m:u"):
            results[bus.loc_name] = {
                "v_pu": bus.GetAttribute("m:u"),
                "v_kv": bus.GetAttribute("m:U"),
                "angle_deg": bus.GetAttribute("m:phiu")
            }
else:
    results["error"] = f"Load flow failed with code {error_code}"

os.makedirs("results", exist_ok=True)
with open("results/voltages.json", "w") as f:
    json.dump(results, f, indent=2)
```
