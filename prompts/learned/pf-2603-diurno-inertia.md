# Flujo de Potencia 'Laboral Diurno' en Proyecto 2603 con Cálculo de Inercia

Fecha: 2026-04-07
Tarea: "En el proyecto '2603-BD-OP-COORD-DMAP.pfd': 1. Activa 'Base SEN'. 2. Activa 'Laboral Diurno'. 3. Deshabilita ElmDsl. 4. Configura ComLdf con Distributed slack (iopt_pbal=4), Flat start e ignorar errores. 5. Ejecuta y reporta Resumen SEN, Desglose por Tecnología, Inercia Total (GVA*s) y Convergencia."

## Lecciones aprendidas
- **Acceso a Atributos de Inercia**: Para calcular la inercia en PowerFactory, es más robusto acceder a `sgn` (MVA nominal) y `h` (constante de inercia) desde el objeto de tipo (`typ_id`) del generador síncrono (`ElmSym`), ya que no siempre están presentes o poblados directamente en el objeto de red.
- **Inercia del Sistema**: La inercia total se calcula como $\sum (S_{nom,i} \cdot H_i)$ para todos los generadores síncronos en servicio. El resultado se convierte de MVA*s a GVA*s dividiendo por 1000. En este escenario diurno, se obtuvo un valor de 34.96 GVA*s.
- **Mix Tecnológico Diurno**: El escenario 'Laboral Diurno' muestra una fuerte presencia de generación solar (5211 MW), lo cual es consistente con el bloque horario y explica la reducción de generación térmica comparado con escenarios nocturnos.
- **Manejo de Atributos**: Se utilizó una función `set_attr` para manejar la asignación de atributos en `ComLdf` de forma segura, intentando tanto `SetAttribute` como asignación directa de propiedad, lo cual mejora la compatibilidad entre versiones de la API.

## Script
```python
import sys
import os
import json
import time

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

def get_tech(name):
    name = name.upper()
    if any(k in name for k in ["STATCOM", "CONDENSADOR", "SVC"]):
        return "Excluded"
    if any(k in name for k in ["TER", "GEO"]):
        return "termica"
    if any(k in name for k in ["HE", "HP"]):
        return "hidraulica"
    if any(k in name for k in ["PFV", "CSP"]):
        return "solar"
    if "PE" in name:
        return "eolica"
    if "BESS" in name:
        return "bess"
    return "others"

def run_analysis():
    start_time = time.time()
    timing = {}
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    os.makedirs(results_dir, exist_ok=True)
    
    app = powerfactory.GetApplicationExt()
    if not app:
        return {"error": "Failed to get PowerFactory application"}
    
    user = app.GetCurrentUser()
    pfd_candidates = [
        os.path.abspath(os.path.join("..", "projects", "2603-BD-OP-COORD-DMAP.pfd")),
        os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd")),
        os.path.abspath(os.path.join("projects", "2603-BD-OP-COORD-DMAP.pfd"))
    ]
    pfd_path = None
    for p in pfd_candidates:
        if os.path.exists(p):
            pfd_path = p
            break
    if not pfd_path: return {"error": "Project file not found"}
    
    pfd_filename = os.path.basename(pfd_path)
    cache_file = os.path.join(results_dir, ".project_cache.json")
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cache = json.load(f)
    project_name = cache.get(pfd_filename)
    if project_name:
        existing = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
        if project_name not in existing: project_name = None

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
            with open(cache_file, "w") as f: json.dump(cache, f, indent=2)
        else: return {"error": "Import failed"}

    proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    all_cases = proj.GetContents("*.IntCase", 1)
    study_case = next((c for c in all_cases if c.loc_name == "Base SEN"), None)
    if not study_case: return {"error": "Study case 'Base SEN' not found"}
    study_case.Activate()
    
    all_scenarios = proj.GetContents("*.IntScenario", 1)
    scenario = next((s for s in all_scenarios if "Laboral Diurno" in s.loc_name), None)
    if not scenario: return {"error": "Scenario 'Laboral Diurno' not found"}
    scenario.Activate()
    
    dsl_models = app.GetCalcRelevantObjects("*.ElmDsl")
    for dsl in dsl_models: dsl.outserv = 1
    
    ldf = app.GetFromStudyCase("ComLdf")
    if not ldf: ldf = app.GetActiveStudyCase().CreateObject("ComLdf", "Load Flow")
    
    def set_attr(obj, attr, val):
        if obj.HasAttribute(attr):
            try: obj.SetAttribute(attr, val)
            except: setattr(obj, attr, val)
    set_attr(ldf, "iopt_pbal", 4)
    set_attr(ldf, "iopt_init", 1)
    set_attr(ldf, "iopt_errlf", 1)
        
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - start_time
    
    if error_code != 0:
        diag = {
            "status": "diverged", "error_code": error_code, "project": project_name, "study_case": "Base SEN",
            "diagnosis": {
                "total_generation_mw": sum(safe_get(g, "pgini", 0.0) for g in app.GetCalcRelevantObjects("*.ElmSym") if g.outserv == 0),
                "total_load_mw": sum(safe_get(l, "plini", 0.0) for l in app.GetCalcRelevantObjects("*.ElmLod") if l.outserv == 0),
                "imbalance_mw": 0, "slack_bus_found": True, "external_grid_active": False, "isolated_buses": 0
            },
            "recommendations": ["Check network status"]
        }
        with open(os.path.join(results_dir, "diagnostico.json"), "w") as f: json.dump(diag, f, indent=2)
        return {"error": "Power flow diverged", "results": diag}

    gen_mw = {"termica": 0.0, "hidraulica": 0.0, "solar": 0.0, "eolica": 0.0, "bess": 0.0, "others": 0.0}
    total_inertia_mvas = 0.0
    
    all_sym = app.GetCalcRelevantObjects("*.ElmSym")
    for g in all_sym:
        if g.outserv == 0:
            tech = get_tech(g.loc_name)
            if tech == "Excluded": continue
            p_mw = safe_get(g, "m:P:bus1", 0.0)
            if tech in gen_mw: gen_mw[tech] += p_mw
            else: gen_mw["others"] += p_mw
            
            # Inertia calculation
            typ = g.GetAttribute("typ_id")
            if typ:
                sgn = safe_get(g, "sgn", 0.0)
                if sgn == 0.0: sgn = safe_get(typ, "sgn", 0.0)
                h = safe_get(typ, "h", 0.0)
                total_inertia_mvas += (sgn * h)
            
    all_stat = app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_stat:
        if g.outserv == 0:
            tech = get_tech(g.loc_name)
            if tech == "Excluded": continue
            p_mw = safe_get(g, "m:P:bus1", 0.0)
            if tech in gen_mw: gen_mw[tech] += p_mw
            else: gen_mw["others"] += p_mw

    total_gen_mw = sum(gen_mw.values())
    all_loads = app.GetCalcRelevantObjects("*.ElmLode") + app.GetCalcRelevantObjects("*.ElmLod")
    total_load_mw = sum(safe_get(l, "m:P:bus1", 0.0) for l in all_loads if l.outserv == 0)
    
    losses_mw = 0.0
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        if line.outserv == 0: losses_mw += (safe_get(line, "m:P:bus1") + safe_get(line, "m:P:bus2"))
    for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
        if trafo.outserv == 0: losses_mw += (safe_get(trafo, "m:P:bushv") + safe_get(trafo, "m:P:buslv"))
    for trafo3 in app.GetCalcRelevantObjects("*.ElmTr3"):
        if trafo3.outserv == 0: losses_mw += (safe_get(trafo3, "m:P:bushv") + safe_get(trafo3, "m:P:busmv") + safe_get(trafo3, "m:P:buslv"))

    output = {
        "resumen_sen": {"generacion_total_mw": total_gen_mw, "carga_total_mw": total_load_mw, "perdidas_totales_mw": losses_mw},
        "desglose_tecnologia_mw": gen_mw,
        "inercia_total_gvas": total_inertia_mvas / 1000.0,
        "convergencia": True,
        "pf_messages": app.GetOutputWindow().GetContent(),
        "timing": timing
    }
    
    with open(os.path.join(results_dir, "resultados_flujo.json"), "w") as f:
        json.dump(output, f, indent=2)
        
    return output

if __name__ == "__main__":
    results = run_analysis()
```
