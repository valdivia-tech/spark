# Flujo de Potencia 2603 Laboral Diurno con Reporte Ejecutivo

Fecha: 2026-04-07
Tarea: "EJECUTAR ESTUDIO EN PROYECTO 2603-BD-OP-COORD-DMAP.pfd ... Configurar Flujo ... Extracción TOP 10 ... Resumen por Zona"

## Lecciones aprendidas
- **Activación de Escenario**: Al activar un escenario en una base de datos de operación (.pfd), PowerFactory aplica automáticamente el despacho y la topología. No es necesario (y puede ser contraproducente) modificar `pgini` o usar `Apply()` si se usa `Activate()`.
- **Detección de Zonas en BD Operación**: Las zonas en estas bases suelen estar organizadas por carpetas (`IntFolder`) o redes (`ElmNet`) que comienzan con códigos numéricos (ej: '00-', '01-', etc.). Realizar una búsqueda recursiva de todos los contenedores (`IntFolder`, `SetFolder`, `ElmNet`) y filtrar por prefijo es una estrategia robusta para agrupar elementos por región.
- **Filtrado de Voltajes**: En sistemas con muchas áreas aisladas (como ocurre tras activar escenarios de operación), el flujo de potencia puede reportar voltajes extremadamente bajos (ej: 1e-21 pu) para barras desconectadas. Es necesario filtrar por un umbral mínimo (ej: > 0.1 pu) para obtener rankings de tensión con sentido físico.
- **Configuración ComLdf**: El uso de `iopt_pbal=4` (Distributed Slack) y `iopt_errlf=1` (Continuar en errores) es esencial para la convergencia en bases de datos reales del CEN que contienen modelos DSL complejos y DLLs de terceros no disponibles.

## Script
```python
import sys
import os
import json
import time
import traceback

# PowerFactory initialization
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)

pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

import powerfactory

def safe_get(obj, attr, default=0.0):
    try:
        if obj.HasAttribute(attr):
            val = obj.GetAttribute(attr)
            return val if val is not None else default
    except:
        pass
    return default

def get_bus_name(obj, port_name):
    try:
        bus = obj.GetAttribute(port_name)
        if bus:
            return bus.loc_name
    except:
        pass
    return "N/A"

def run_analysis():
    start_time = time.time()
    timing = {}
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    app = powerfactory.GetApplicationExt()
    if not app:
        return {"error": "Failed to get PowerFactory application"}
    
    user = app.GetCurrentUser()
    pfd_paths = [
        os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd")),
        os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
    ]
    pfd_path = None
    for p in pfd_paths:
        if os.path.exists(p):
            pfd_path = p
            break
            
    if not pfd_path:
        return {"error": "Project file not found"}
    
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
        new_projects = projects_after - projects_before
        if new_projects:
            project_name = list(new_projects)[0]
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        else:
            return {"error": "Import failed"}

    proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
    if not proj:
        return {"error": "Project not found"}
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # Study Case
    study_case = next((c for c in proj.GetContents("*.IntCase", 1) if c.loc_name == "Base SEN"), None)
    if not study_case:
        return {"error": "Study case 'Base SEN' not found"}
    study_case.Activate()
    
    # Scenario
    scenario = next((s for s in proj.GetContents("*.IntScenario", 1) if "Laboral Diurno" in s.loc_name), None)
    if not scenario:
        return {"error": "Scenario 'Laboral Diurno' not found"}
    scenario.Activate()
    
    # Load Flow config
    ldf = app.GetFromStudyCase("ComLdf")
    if not ldf:
        ldf = app.GetActiveStudyCase().CreateObject("ComLdf", "LDF")
    
    ldf.iopt_net = 0    # AC
    ldf.iopt_pbal = 4   # Distributed Slack
    ldf.iopt_init = 1   # Flat start
    if ldf.HasAttribute('iopt_errlf'):
        ldf.SetAttribute('iopt_errlf', 1)  # Continue on errors
        
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - start_time
    pf_messages = app.GetOutputWindow().GetContent()

    report = {}
    
    # 1. TOP 10 CENTRALES
    gens = []
    for g in (app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")):
        if safe_get(g, "outserv", 0) == 0:
            p_mw = safe_get(g, "m:P:bus1", 0.0)
            substation = "N/A"
            grid = g.GetAttribute("cpGrid")
            if grid: substation = grid.loc_name
            
            gens.append({
                "nombre": g.loc_name,
                "tipo": safe_get(g, "cCategory", "N/A"),
                "generacion_mw": p_mw,
                "subestacion": substation
            })
    gens.sort(key=lambda x: x["generacion_mw"], reverse=True)
    report["top_10_centrales"] = gens[:10]

    # 2. TOP 10 LÍNEAS
    lines = []
    for l in app.GetCalcRelevantObjects("*.ElmLne"):
        if safe_get(l, "outserv", 0) == 0:
            lines.append({
                "nombre": l.loc_name,
                "loading_pct": safe_get(l, "c:loading", 0.0),
                "p_mw": safe_get(l, "m:P:bus1", 0.0),
                "q_mvar": safe_get(l, "m:Q:bus1", 0.0),
                "bus1": get_bus_name(l, "bus1"),
                "bus2": get_bus_name(l, "bus2")
            })
    lines.sort(key=lambda x: x["loading_pct"], reverse=True)
    report["top_10_lineas"] = lines[:10]

    # 3. TOP 10 TRANSFORMADORES
    trafos = []
    for t in (app.GetCalcRelevantObjects("*.ElmTr2") + app.GetCalcRelevantObjects("*.ElmTr3")):
        if safe_get(t, "outserv", 0) == 0:
            trafos.append({
                "nombre": t.loc_name,
                "loading_pct": safe_get(t, "c:loading", 0.0),
                "bus_hv": get_bus_name(t, "bushv"),
                "bus_lv": get_bus_name(t, "buslv")
            })
    trafos.sort(key=lambda x: x["loading_pct"], reverse=True)
    report["top_10_transformadores"] = trafos[:10]

    # 4 & 5. TOP BARRAS
    buses = []
    for b in app.GetCalcRelevantObjects("*.ElmTerm"):
        uknom = safe_get(b, "uknom", 0.0)
        if uknom >= 66.0:
            u_pu = safe_get(b, "m:u", 0.0)
            if u_pu > 0.1:
                buses.append({"nombre": b.loc_name, "kv_nominal": uknom, "u_pu": u_pu})
    
    buses_low = sorted(buses, key=lambda x: x["u_pu"])
    buses_high = sorted(buses, key=lambda x: x["u_pu"], reverse=True)
    report["top_10_barras_baja_tension"] = buses_low[:10]
    report["top_10_barras_alta_tension"] = buses_high[:10]

    # 6. RESUMEN POR ZONA
    zones = [
        '00-Norte Grande', '01-Atacama', '02-Coquimbo', '03-Valparaiso',
        '04-Metropolitana', '05-O Higgins', '06-Maule', '07-Nuble',
        '08-Biobio', '09-Araucania', '10-Los Rios', '11-Los Lagos',
        '12-Aysen', '13-Magallanes'
    ]
    zone_gen = {z: 0.0 for z in zones}
    
    all_objs = proj.GetContents("*.IntFolder", 1) + proj.GetContents("*.SetFolder", 1) + proj.GetContents("*.ElmNet", 1)
    
    for z in zones:
        prefix = z[:3]
        for obj in all_objs:
            if obj.loc_name.startswith(prefix):
                gs = obj.GetContents("*.ElmSym", 1) + obj.GetContents("*.ElmGenstat", 1)
                for g in gs:
                    if safe_get(g, "outserv", 0) == 0:
                        zone_gen[z] += abs(safe_get(g, "m:P:bus1", 0.0))

    report["resumen_por_zona"] = zone_gen
    report["pf_messages"] = pf_messages
    report["timing"] = timing
    report["status"] = "success"

    with open(os.path.join(results_dir, "reporte_ejecutivo.json"), "w") as f:
        json.dump(report, f, indent=2)
    
    return report

if __name__ == "__main__":
    try:
        run_analysis()
    except Exception as e:
        results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
        os.makedirs(results_dir, exist_ok=True)
        with open(os.path.join(results_dir, "error.json"), "w") as f:
            json.dump({"error": str(e), "traceback": traceback.format_exc()}, f, indent=2)
```
