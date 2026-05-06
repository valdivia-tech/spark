# Exploración de Proyecto - Inventario de Scripts y Referencias Externas
Fecha: 2026-04-06
Tarea: "Find and list all DPL scripts and objects referencing external data files in project 2603-BD-OP-COORD-DMAP.pfd"

## Lecciones aprendidas
- Importar `powerfactory` debe hacerse DESPUÉS de modificar `sys.path` para incluir `POWERFACTORY_PATH`, de lo contrario fallará con `ModuleNotFoundError`.
- El uso de `GetContents("*.ClassName", 1)` es la forma más eficiente de encontrar todos los objetos de una clase específica recursivamente dentro del proyecto.
- Los atributos comunes para rutas de archivos externos son `f_file` (usado en `IntCom`, `ComImport`) y ocasionalmente `g_file`.
- `GetFullName()` devuelve la ruta completa del objeto dentro de la jerarquía de PowerFactory.

## Script
```python
import sys, os, time, json

def get_obj_path(obj):
    """Returns the full path of an object in the project."""
    try:
        return obj.GetFullName()
    except:
        return obj.loc_name

def explore_project():
    start_time = time.time()
    
    # PF Init
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

    timing = {}
    load_start = time.time()
    
    user = app.GetCurrentUser()
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
    pfd_filename = os.path.basename(pfd_path)

    # Import and activate project (using cache logic)
    # ... logic omitted for brevity in summary, but present in full script ...
    
    proj.Activate()
    timing["load_project_seconds"] = time.time() - load_start
    
    extract_start = time.time()
    
    # 1. Find all DPL scripts
    dpl_scripts = proj.GetContents("*.ComDpl", 1)
    dpls_info = [{"name": d.loc_name, "path": get_obj_path(d)} for d in dpl_scripts]
        
    # 2. Check for objects referencing external data
    external_refs = []
    classes_to_check = ["*.IntCom", "*.ComImport", "*.IntForm"]
    for cls in classes_to_check:
        objs = proj.GetContents(cls, 1)
        for obj in objs:
            ref_path = None
            if obj.HasAttribute("f_file"):
                ref_path = obj.GetAttribute("f_file")
            elif obj.HasAttribute("g_file"):
                ref_path = obj.GetAttribute("g_file")
                
            external_refs.append({
                "class": obj.GetClassName(),
                "name": obj.loc_name,
                "project_path": get_obj_path(obj),
                "referenced_file": str(ref_path) if ref_path else "None"
            })
            
    timing["extract_results_seconds"] = time.time() - extract_start
    # ... save to JSON ...
```
