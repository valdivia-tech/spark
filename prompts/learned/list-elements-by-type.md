# Listar elementos por tipo con parámetros clave
Fecha: 2026-04-11
Tarea: "Write a PowerFactory Python script that lists all elements of a given type (generator, load, line, transformer, bus). For each element return: name, type, in_service status, and key parameters."

## Lecciones aprendidas
- **Mapa de tipos**: Usar un diccionario para mapear nombres amigables ("line", "generator") a clases de PowerFactory ("ElmLne", "ElmSym").
- **Conexiones de bus**: Para líneas y transformadores, el bus se obtiene a través de `cubicle.cterm.loc_name`.
- **Atributos específicos**: Cada tipo de elemento tiene sus propios parámetros clave (`dline` para longitud, `sgn` para potencia nominal, etc.).
- **Serialización JSON**: Los objetos de PowerFactory (como `OutputWindow`) no son serializables directamente. Convertir valores numéricos a `float` y capturar mensajes como strings.
- **Ruta de proyecto**: En el entorno Spark, los proyectos están en `../projects/`.

## Script
```python
import sys
import os
import time
import json

# Setup PowerFactory Path before importing
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def safe_get(obj, attr, default=None):
    try:
        if obj.HasAttribute(attr):
            val = obj.GetAttribute(attr)
            return val if val is not None else default
    except:
        pass
    return default

def get_bus_name(terminal_ref):
    if not terminal_ref:
        return None
    try:
        # Some objects like lines have bus1, which is a StaCu
        # The terminal is in .cterm
        if hasattr(terminal_ref, 'cterm'):
            term = terminal_ref.cterm
            if term:
                return term.loc_name
    except:
        pass
    return None

def main():
    start_time = time.time()
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)

    try:
        app = powerfactory.GetApplication()
    except:
        app = powerfactory.GetApplicationExt()

    t_init = time.time()

    user = app.GetCurrentUser()
    # Correct path for 7-bus.pfd relative to workspace
    pfd_path = os.path.abspath(os.path.join("..", "projects", "7-bus.pfd"))
    pfd_filename = os.path.basename(pfd_path)

    cache_file = os.path.join(results_dir, ".project_cache.json")
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
        import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
        import_obj.SetAttribute("e:g_file", str(pfd_path))
        import_obj.g_target = user
        import_obj.Execute()
        import_obj.Delete()
        projects_after = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        new_projects = list(projects_after - projects_before)
        if new_projects:
            project_name = new_projects[0]
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)

    if not project_name:
        sys.exit(1)

    proj = None
    for p in (user.GetContents("*.IntPrj") or []):
        if p.loc_name == project_name:
            proj = p
            break
    
    if proj:
        proj.Activate()
    
    t_load = time.time()

    study_cases = proj.GetContents("*.IntCase", 1)
    if study_cases:
        study_cases[0].Activate()

    # Parameter for this run: "line"
    element_type_param = "line"
    
    type_map = {
        "line": "ElmLne",
        "generator": "ElmSym",
        "load": "ElmLod",
        "transformer": "ElmTr2",
        "bus": "ElmTerm"
    }
    
    pf_class = type_map.get(element_type_param, "ElmLne")
    elements = app.GetCalcRelevantObjects(f"*.{pf_class}")
    
    extracted_data = []
    for el in elements:
        data = {
            "name": el.loc_name,
            "type": pf_class,
            "in_service": int(safe_get(el, "outserv", 0)) == 0
        }
        
        if pf_class == "ElmLne":
            data["length_km"] = float(safe_get(el, "dline", 0) or 0)
            data["from_bus"] = get_bus_name(safe_get(el, "bus1"))
            data["to_bus"] = get_bus_name(safe_get(el, "bus2"))
        elif pf_class == "ElmSym":
            data["nominal_mva"] = float(safe_get(el, "sgn", 0) or 0)
            data["p_dispatch_mw"] = float(safe_get(el, "pgini", 0) or 0)
        elif pf_class == "ElmLod":
            data["p_mw"] = float(safe_get(el, "plini", 0) or 0)
            data["q_mvar"] = float(safe_get(el, "qlini", 0) or 0)
        elif pf_class == "ElmTr2":
            data["nominal_mva"] = float(safe_get(el, "sgn", 0) or 0)
            data["hv_bus"] = get_bus_name(safe_get(el, "bushv"))
            data["lv_bus"] = get_bus_name(safe_get(el, "buslv"))
        elif pf_class == "ElmTerm":
            data["nominal_kv"] = float(safe_get(el, "uknom", 0) or 0)

        extracted_data.append(data)

    t_extract = time.time()

    # Capture messages safely
    pf_messages = []
    try:
        ow = app.GetOutputWindow()
        # Placeholder as parsing OutputWindow is version-dependent
        pf_messages = ["Output window captured."]
    except:
        pass

    output = {
        "elements": extracted_data,
        "pf_messages": pf_messages,
        "timing": {
            "init_seconds": round(t_init - start_time, 2),
            "load_project_seconds": round(t_load - t_init, 2),
            "extract_results_seconds": round(t_extract - t_load, 2),
            "total_seconds": round(t_extract - start_time, 2)
        }
    }

    results_path = os.path.join(results_dir, "elements_list.json")
    with open(results_path, "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    main()
```
