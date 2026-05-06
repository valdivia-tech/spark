# Ajuste de Tap de Transformador (ElmTr2)
Fecha: 2025-05-15
Tarea: "Escribir un script que ajuste el tap de un transformer (ElmTr2), validando contra los límites del tipo (TypTr2)."

## Lecciones aprendidas
- **Atributos de Tap**: En `ElmTr2`, la posición se controla con `nntap` (int).
- **Atributos del Tipo**: Los límites se encuentran en el objeto `typ_id` (clase `TypTr2`):
  - `ntpmn`: Límite inferior (min).
  - `ntpmx`: Límite superior (max).
  - `nntap0`: Posición neutral.
  - `dutap`: Paso por tap en porcentaje.
- **Validación**: Es fundamental validar `nntap` antes de asignarlo, ya que valores fuera de rango pueden no ser aceptados o causar inconsistencias.
- **Output Window**: `app.GetOutputWindow()` retorna un objeto `IntOut`. Para extraer los mensajes, se usa `.GetMessages(0)`.

## Script
```python
import sys, os, json, time

def get_pf_messages(app):
    """Safely extract messages from the PowerFactory output window."""
    try:
        out = app.GetOutputWindow()
        if hasattr(out, "GetMessages"):
            # 0: all, 1: information, 2: warnings, 3: errors
            return [str(m) for m in out.GetMessages(0)]
    except:
        pass
    return []

def main():
    t_start = time.time()
    
    # 1. Initialize PowerFactory
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
    
    RESULTS_DIR = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(RESULTS_DIR, exist_ok=True)
    
    timing = {}
    
    # 2. Load project using cache
    t0 = time.time()
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
    timing["load_project_seconds"] = time.time() - t0

    # 3. Find transformer and set tap
    t0 = time.time()
    trafos = app.GetCalcRelevantObjects("*.ElmTr2")
    if not trafos:
        trafos = proj.GetContents("*.ElmTr2", 1)
        
    if not trafos:
        results = {
            "status": "failed",
            "error": "No transformer (ElmTr2) found in project",
            "pf_messages": get_pf_messages(app)
        }
        with open(os.path.join(RESULTS_DIR, "tap_results.json"), "w") as f:
            json.dump(results, f, indent=2)
        return

    trafo = trafos[0]
    trafo_name = trafo.loc_name
    
    # Read type info
    typ = trafo.typ_id
    if not typ:
        results = {
            "status": "failed",
            "error": f"Transformer {trafo_name} has no type (typ_id)",
            "pf_messages": get_pf_messages(app)
        }
        with open(os.path.join(RESULTS_DIR, "tap_results.json"), "w") as f:
            json.dump(results, f, indent=2)
        return

    # Tap limits and settings from TypTr2
    ntpmn = int(typ.GetAttribute("ntpmn") if typ.HasAttribute("ntpmn") else -10)
    ntpmx = int(typ.GetAttribute("ntpmx") if typ.HasAttribute("ntpmx") else 10)
    nntap0 = int(typ.GetAttribute("nntap0") if typ.HasAttribute("nntap0") else 0)
    dutap = float(typ.GetAttribute("dutap") if typ.HasAttribute("dutap") else 0.0)
    
    requested_tap = 0 # From parameters
    
    # Read current tap
    initial_tap = int(trafo.GetAttribute("nntap") or 0)
    
    # Validation
    validation_error = None
    if requested_tap < ntpmn or requested_tap > ntpmx:
        validation_error = f"Requested tap {requested_tap} is out of limits [{ntpmn}, {ntpmx}]"
    
    final_tap = initial_tap
    if not validation_error:
        trafo.SetAttribute("nntap", requested_tap)
        final_tap = int(trafo.GetAttribute("nntap") or 0)
    
    timing["set_tap_seconds"] = time.time() - t0
    
    # Save results
    results = {
        "status": "success" if not validation_error else "validation_failed",
        "transformer": trafo_name,
        "type": typ.loc_name,
        "limits": {
            "min": ntpmn,
            "max": ntpmx,
            "neutral": nntap0,
            "step_percent": dutap
        },
        "initial_tap": initial_tap,
        "requested_tap": requested_tap,
        "final_tap": final_tap,
        "validation_error": validation_error,
        "pf_messages": get_pf_messages(app),
        "timing": timing
    }
    
    with open(os.path.join(RESULTS_DIR, "tap_results.json"), "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
```
