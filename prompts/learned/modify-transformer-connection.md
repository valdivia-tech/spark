# Modificar Conexión de Transformador (TypTr2)
Fecha: 2026-05-20
Tarea: "Escribir un script que modifique la conexión de los devanados (HV, LV) de un tipo de transformador (TypTr2)."

## Lecciones aprendidas
- **Ubicación de Atributos**: Las conexiones de los devanados residen en el **Tipo** (`TypTr2`), no en el elemento (`ElmTr2`).
- **Atributos Clave**:
  - HV (Lado de alta): `nt2ag`
  - LV (Lado de baja): `nt2ph`
- **Mapeo de Valores**:
  - `0`: Y (Estrella)
  - `1`: YN (Estrella con neutro)
  - `2`: D (Triángulo/Delta)
- **Impacto**: Modificar el tipo afecta a todos los transformadores que utilicen dicho tipo en el proyecto.

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
    pfd_path = os.path.join(os.environ["SPARK_PROJECTS_DIR"], "7-bus.pfd")
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

    # 3. Parameters and Mapping
    # Y=0, YN=1, D=2
    connection_map = {"Y": 0, "YN": 1, "D": 2}
    hv_conn_str = "YN"
    lv_conn_str = "D"
    
    hv_conn_val = connection_map.get(hv_conn_str)
    lv_conn_val = connection_map.get(lv_conn_str)
    
    if hv_conn_val is None or lv_conn_val is None:
        raise ValueError(f"Invalid connection type requested: HV={hv_conn_str}, LV={lv_conn_str}")

    # 4. Find Transformer Type and Modify
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
        with open(os.path.join(RESULTS_DIR, "modify_connection_results.json"), "w") as f:
            json.dump(results, f, indent=2)
        return

    # In 7-bus, there is typically one main transformer type. 
    # We'll update the type of the first transformer found.
    trafo = trafos[0]
    typ = trafo.typ_id
    
    if not typ:
        results = {
            "status": "failed",
            "error": f"Transformer {trafo.loc_name} has no type (typ_id)",
            "pf_messages": get_pf_messages(app)
        }
        with open(os.path.join(RESULTS_DIR, "modify_connection_results.json"), "w") as f:
            json.dump(results, f, indent=2)
        return

    # Save initial state for reporting
    initial_hv = int(typ.GetAttribute("nt2ag") or 0)
    initial_lv = int(typ.GetAttribute("nt2ph") or 0)
    
    # Apply changes
    # HV: nt2ag, LV: nt2ph
    typ.SetAttribute("nt2ag", hv_conn_val)
    typ.SetAttribute("nt2ph", lv_conn_val)
    
    final_hv = int(typ.GetAttribute("nt2ag") or 0)
    final_lv = int(typ.GetAttribute("nt2ph") or 0)
    
    timing["modify_connection_seconds"] = time.time() - t0
    
    # 5. Report Results
    results = {
        "status": "success",
        "transformer": trafo.loc_name,
        "type": typ.loc_name,
        "initial_connections": {
            "hv": initial_hv,
            "lv": initial_lv
        },
        "requested_connections": {
            "hv": hv_conn_val,
            "lv": lv_conn_val,
            "hv_str": hv_conn_str,
            "lv_str": lv_conn_str
        },
        "final_connections": {
            "hv": final_hv,
            "lv": final_lv
        },
        "pf_messages": get_pf_messages(app),
        "timing": timing
    }
    
    with open(os.path.join(RESULTS_DIR, "modify_connection_results.json"), "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    main()
```
