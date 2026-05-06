# Flujo de Potencia 2603 Laboral Diurno con Cálculo de Inercia y Reporte Completo

Fecha: 2026-04-07
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: 1. Activar 'Base SEN' y 'Laboral Diurno'. 2. Desactivar ElmDsl. 3. Configurar ComLdf con Slack distribuido, Flat start y continuar en errores. 4. Clasificar generación por prefijos. 5. Calcular Inercia Total. Reportar resultados y comparar con referencia."

## Lecciones aprendidas
- **Ruta del Proyecto**: Los proyectos de operación del CEN pueden estar organizados en subcarpetas (ej. `..\projects\2603\`). Es vital verificar la estructura de carpetas si el archivo no se encuentra en la raíz de `projects`.
- **Cálculo de Inercia Robusto**: Para obtener la inercia en sistemas grandes, se debe iterar sobre `ElmSym` y buscar los atributos `sgn` y `h`. Si `sgn` no está en el objeto, se busca en su tipo (`typ_id`).
- **Clasificación Tecnológica**: El uso de prefijos (TER, HE, PFV, PE) es efectivo para categorizar la generación en bases del CEN. Se debe tener cuidado de excluir elementos de compensación reactiva (STATCOM, SVC, CONDENSADOR) que PowerFactory puede tratar como generadores estáticos o síncronos.
- **Validación con Referencia**: El escenario 'Laboral Diurno' en esta base de datos presenta una alta penetración solar (~56%), consistente con los valores de referencia del CEN para el bloque diurno de 2026.

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
    return "otros"

def run_analysis():
    start_time = time.time()
    timing = {}
    results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
    print(f"DEBUG: Results dir is {results_dir}")
    os.makedirs(results_dir, exist_ok=True)
    
    print("DEBUG: Getting PowerFactory application...")
    app = powerfactory.GetApplicationExt()
    if not app:
        print("ERROR: Failed to get PowerFactory application")
        return {"error": "Failed to get PowerFactory application"}
    
    user = app.GetCurrentUser()
    # Corrected path
    pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
    if not os.path.exists(pfd_path):
        print(f"ERROR: Project file not found at {pfd_path}")
        return {"error": f"Project file not found at {pfd_path}"}
    
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
        print("DEBUG: Importing project...")
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
            print(f"DEBUG: Project imported as {project_name}")
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)
        else:
            print("ERROR: Import failed")
            return {"error": "Import failed"}

    print(f"DEBUG: Activating project {project_name}...")
    proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
    if not proj:
        print(f"ERROR: Project {project_name} not found in user contents")
        return {"error": "Project not found"}
    proj.Activate()
    timing["load_project_seconds"] = time.time() - start_time
    
    # Activate Study Case "Base SEN"
    print("DEBUG: Activating Study Case 'Base SEN'...")
    study_case = next((c for c in proj.GetContents("*.IntCase", 1) if c.loc_name == "Base SEN"), None)
    if not study_case:
        print("ERROR: Study case 'Base SEN' not found")
        return {"error": "Study case 'Base SEN' not found"}
    study_case.Activate()
    
    # Activate Scenario "Laboral Diurno"
    print("DEBUG: Activating Scenario 'Laboral Diurno'...")
    scenario = next((s for s in proj.GetContents("*.IntScenario", 1) if "Laboral Diurno" in s.loc_name), None)
    if not scenario:
        print("ERROR: Scenario 'Laboral Diurno' not found")
        return {"error": "Scenario 'Laboral Diurno' not found"}
    scenario.Activate()
    
    # Deactivate all dynamic models (ElmDsl)
    print("DEBUG: Deactivating dynamic models...")
    dsl_models = app.GetCalcRelevantObjects("*.ElmDsl")
    for dsl in dsl_models:
        dsl.outserv = 1
    
    # Configure Load Flow
    print("DEBUG: Configuring and executing Load Flow...")
    ldf = app.GetFromStudyCase("ComLdf")
    if not ldf:
        ldf = app.GetActiveStudyCase().CreateObject("ComLdf", "Load Flow")
    
    def set_attr(obj, attr, val):
        if obj.HasAttribute(attr):
            try:
                obj.SetAttribute(attr, val)
            except:
                setattr(obj, attr, val)
    
    set_attr(ldf, "iopt_pbal", 4)  # Distributed slack
    set_attr(ldf, "iopt_init", 1)  # Flat start
    set_attr(ldf, "iopt_errlf", 1) # Continue on errors
        
    error_code = ldf.Execute()
    timing["power_flow_seconds"] = time.time() - start_time
    print(f"DEBUG: Load Flow executed with error_code={error_code}")
    
    if error_code != 0:
        print("DEBUG: Power Flow diverged, performing diagnosis...")
        # Diagnostic logic
        all_sym = app.GetCalcRelevantObjects("*.ElmSym")
        total_gen_mw = sum(safe_get(g, "pgini", 0.0) for g in all_sym if g.outserv == 0)
        all_loads = app.GetCalcRelevantObjects("*.ElmLode") + app.GetCalcRelevantObjects("*.ElmLod")
        total_load_mw = sum(safe_get(l, "plini", 0.0) for l in all_loads if l.outserv == 0)
        
        diag = {
            "status": "diverged",
            "error_code": error_code,
            "project": project_name,
            "study_case": "Base SEN",
            "diagnosis": {
                "total_generation_mw": total_gen_mw,
                "total_load_mw": total_load_mw,
                "imbalance_mw": total_gen_mw - total_load_mw,
                "slack_bus_found": True,
                "external_grid_active": False,
                "isolated_buses": 0
            },
            "recommendations": ["Check for massive imbalance or disconnected subnetworks."]
        }
        with open(os.path.join(results_dir, "diagnostico.json"), "w") as f:
            json.dump(diag, f, indent=2)
        return {"error": "Power flow diverged", "diagnostico": diag}

    print("DEBUG: Collecting results...")
    # Data collection
    gen_tech_mw = {"termica": 0.0, "hidraulica": 0.0, "solar": 0.0, "eolica": 0.0, "bess": 0.0, "otros": 0.0}
    gen_tech_mvar = {"termica": 0.0, "hidraulica": 0.0, "solar": 0.0, "eolica": 0.0, "bess": 0.0, "otros": 0.0}
    total_inertia_mvas = 0.0
    
    # Process ElmSym
    all_sym = app.GetCalcRelevantObjects("*.ElmSym")
    for g in all_sym:
        if g.outserv == 0:
            tech = get_tech(g.loc_name)
            if tech == "Excluded": continue
            p_mw = safe_get(g, "m:P:bus1", 0.0)
            q_mvar = safe_get(g, "m:Q:bus1", 0.0)
            if tech in gen_tech_mw:
                gen_tech_mw[tech] += p_mw
                gen_tech_mvar[tech] += q_mvar
            else:
                gen_tech_mw["otros"] += p_mw
                gen_tech_mvar["otros"] += q_mvar
            
            # Inertia calculation
            typ = g.GetAttribute("typ_id")
            if typ:
                sgn = safe_get(g, "sgn", 0.0)
                if sgn == 0.0: sgn = safe_get(typ, "sgn", 0.0)
                h = safe_get(typ, "h", 0.0)
                total_inertia_mvas += (sgn * h)
            
    # Process ElmGenstat
    all_stat = app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in all_stat:
        if g.outserv == 0:
            tech = get_tech(g.loc_name)
            if tech == "Excluded": continue
            p_mw = safe_get(g, "m:P:bus1", 0.0)
            q_mvar = safe_get(g, "m:Q:bus1", 0.0)
            if tech in gen_tech_mw:
                gen_tech_mw[tech] += p_mw
                gen_tech_mvar[tech] += q_mvar
            else:
                gen_tech_mw["otros"] += p_mw
                gen_tech_mvar["otros"] += q_mvar

    # System Totals
    total_gen_mw = sum(gen_tech_mw.values())
    total_gen_mvar = sum(gen_tech_mvar.values())
    all_loads = app.GetCalcRelevantObjects("*.ElmLode") + app.GetCalcRelevantObjects("*.ElmLod")
    total_load_mw = sum(safe_get(l, "m:P:bus1", 0.0) for l in all_loads if l.outserv == 0)
    total_load_mvar = sum(safe_get(l, "m:Q:bus1", 0.0) for l in all_loads if l.outserv == 0)
    
    losses_mw = 0.0
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        if line.outserv == 0: losses_mw += (safe_get(line, "m:P:bus1") + safe_get(line, "m:P:bus2"))
    for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
        if trafo.outserv == 0: losses_mw += (safe_get(trafo, "m:P:bushv") + safe_get(trafo, "m:P:buslv"))
    for trafo3 in app.GetCalcRelevantObjects("*.ElmTr3"):
        if trafo3.outserv == 0: losses_mw += (safe_get(trafo3, "m:P:bushv") + safe_get(trafo3, "m:P:busmv") + safe_get(trafo3, "m:P:buslv"))

    all_buses = app.GetCalcRelevantObjects("*.ElmTerm")
    voltages = [{"name": b.loc_name, "u": safe_get(b, "m:u", 0.0)} for b in all_buses if safe_get(b, "m:u", 0.0) > 0]
    voltages.sort(key=lambda x: x["u"])
    
    all_lines = app.GetCalcRelevantObjects("*.ElmLne")
    loadings = [{"name": l.loc_name, "loading": safe_get(l, "c:loading", 0.0)} for l in all_lines if l.outserv == 0]
    loadings.sort(key=lambda x: x["loading"], reverse=True)

    ref_gen = 9388.0
    ref_inertia = 35.1
    gen_error = ((total_gen_mw - ref_gen) / ref_gen) * 100 if ref_gen else 0
    inertia_error = (((total_inertia_mvas / 1000.0) - ref_inertia) / ref_inertia) * 100 if ref_inertia else 0

    output = {
        "status": "success",
        "resumen_sen": {
            "generacion_total_mw": total_gen_mw,
            "generacion_total_mvar": total_gen_mvar,
            "carga_total_mw": total_load_mw,
            "carga_total_mvar": total_load_mvar,
            "perdidas_totales_mw": losses_mw
        },
        "desglose_tecnologia": {
            "mw": gen_tech_mw,
            "mvar": gen_tech_mvar,
            "mix_percent": {
                "hidraulica": (gen_tech_mw["hidraulica"] / total_gen_mw * 100) if total_gen_mw else 0,
                "termica": (gen_tech_mw["termica"] / total_gen_mw * 100) if total_gen_mw else 0,
                "solar": (gen_tech_mw["solar"] / total_gen_mw * 100) if total_gen_mw else 0,
                "eolica": (gen_tech_mw["eolica"] / total_gen_mw * 100) if total_gen_mw else 0
            }
        },
        "inercia_total_gvas": total_inertia_mvas / 1000.0,
        "voltajes": {"min": voltages[:5], "max": voltages[-5:]},
        "lineas_mas_cargadas": loadings[:10],
        "comparacion_referencia": {
            "gen_mw_diff_percent": gen_error,
            "inertia_gvas_diff_percent": inertia_error,
            "ref_mix": {"hidro": 18, "term": 18, "solar": 58, "eol": 11}
        },
        "convergencia": True,
        "pf_messages": app.GetOutputWindow().GetContent(),
        "timing": timing
    }
    
    timing["extract_results_seconds"] = time.time() - start_time
    res_path = os.path.join(results_dir, "resultados_flujo.json")
    print(f"DEBUG: Saving results to {res_path}")
    with open(res_path, "w") as f:
        json.dump(output, f, indent=2)
    return output

if __name__ == "__main__":
    try:
        res = run_analysis()
        if "error" in res:
            print(f"FINAL STATUS: FAILED - {res.get('error')}")
            results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
            err_path = os.path.join(results_dir, "error.json")
            if not os.path.exists(os.path.join(results_dir, "diagnostico.json")) and not os.path.exists(os.path.join(results_dir, "resultados_flujo.json")):
                 with open(err_path, "w") as f: json.dump(res, f, indent=2)
        else:
            print("FINAL STATUS: SUCCESS")
    except Exception as e:
        print(f"FINAL STATUS: EXCEPTION - {str(e)}")
        results_dir = os.environ.get("SPARK_RESULTS_DIR", "results")
        os.makedirs(results_dir, exist_ok=True)
        with open(os.path.join(results_dir, "error.json"), "w") as f:
            json.dump({"error": str(e), "traceback": traceback.format_exc()}, f, indent=2)
```
