# Flujo de Potencia con Asignación Emergencia de Slack en 2603
Fecha: 2026-04-06
Tarea: "Activar Caso 'Base SEN', Escenario 'Laboral Diurno', Deshabilitar ElmDsl, Asignar Slack Manual y Correr Flujo AC."

## Lecciones aprendidas
- **Déficit Estructural**: A diferencia de intentos previos donde se detectaba un déficit de ~4 GW, en esta ejecución con el escenario 'Laboral Diurno' correctamente activado, el desbalance inicial fue de **+266.77 MW** (Generación: 9158 MW, Carga: 8892 MW).
- **Sensibilidad al Slack**: Se seleccionó 'TER ANGAMOS U1' como Slack siguiendo el criterio de potencia nominal (sgn). Sin embargo, al configurar `ip_ctrl=0` (según instrucción del usuario), el flujo divergió. En PowerFactory, `ip_ctrl=0` para un ElmSym suele ser control PV (Power Control), mientras que Slack suele ser `ip_ctrl=1` (Slack Control).
- **Persistencia de Divergencia**: A pesar de tener un desbalance relativamente pequeño (~3%), la red divergió. Esto puede deberse a la fragmentación de la red en múltiples islas al desactivar modelos DSL o a la configuración del nodo de referencia.

## Script
```python
import sys
import os
import time
import json

def run():
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
    
    if not app:
        return

    start_time = time.time()
    results = {
        "project": "2603-BD-OP-COORD-DMAP",
        "steps": [],
        "timing": {},
        "status": "unknown"
    }

    try:
        user = app.GetCurrentUser()
        pfd_path = os.path.abspath(os.path.join("..", "projects", "2603", "2603-BD-OP-COORD-DMAP.pfd"))
        pfd_filename = os.path.basename(pfd_path)
        
        cache_file = os.path.join("results", ".project_cache.json")
        os.makedirs("results", exist_ok=True)
        cache = {}
        if os.path.exists(cache_file):
            with open(cache_file) as f:
                try:
                    cache = json.load(f)
                except:
                    cache = {}

        project_name = cache.get(pfd_filename)
        if project_name:
            existing = {p.loc_name for p in (user.GetContents("*.IntPrj") or [])}
            if project_name not in existing:
                project_name = None

        if not project_name:
            import_obj = user.CreateObject('CompfdImport', 'ImportPfd')
            import_obj.SetAttribute("e:g_file", str(pfd_path))
            import_obj.g_target = user
            import_obj.Execute()
            import_obj.Delete()
            for p in user.GetContents("*.IntPrj"):
                if p.loc_name not in cache.values():
                    project_name = p.loc_name
                    break
            cache[pfd_filename] = project_name
            with open(cache_file, "w") as f:
                json.dump(cache, f, indent=2)

        proj = next((p for p in user.GetContents("*.IntPrj") if p.loc_name == project_name), None)
        proj.Activate()
        
        cases = proj.GetContents("*.IntCase", 1)
        study_case = next((c for c in cases if c.loc_name == "Base SEN"), None)
        study_case.Activate()
        
        scenarios = proj.GetContents("*.IntScenario", 1) + proj.GetContents("*.ElmScenario", 1)
        scenario = next((s for s in scenarios if s.loc_name == "Laboral Diurno"), None)
        if scenario:
            scenario.Activate()
        
        dsl_models = app.GetCalcRelevantObjects("*.ElmDsl")
        for dsl in dsl_models:
            dsl.outserv = 1
        
        gens = app.GetCalcRelevantObjects("*.ElmSym")
        active_gens = [g for g in gens if g.outserv == 0]
        
        def get_sgn(g):
            for attr in ["sgn", "s_nom", "gn", "pgini"]:
                if g.HasAttribute(attr):
                    val = g.GetAttribute(attr)
                    if val: return val
            return 0

        if active_gens:
            slack_gen = max(active_gens, key=get_sgn)
        else:
            slack_gen = gens[0]
            slack_gen.outserv = 0
        
        slack_gen.ip_ctrl = 0 # User requested 0
        results["slack_machine"] = slack_gen.loc_name
        results["slack_sgn"] = get_sgn(slack_gen)
        
        ldf = app.GetFromStudyCase("ComLdf")
        ldf.iopt_init = 1
        ldf.iopt_errlf = 1
        ldf.iopt_at = 1
        
        total_gen_mw = sum(g.GetAttribute("pgini") for g in app.GetCalcRelevantObjects("*.ElmSym") if not g.outserv) + \
                       sum(g.GetAttribute("pgini") for g in app.GetCalcRelevantObjects("*.ElmGenstat") if not g.outserv)
        total_load_mw = sum(l.GetAttribute("plini") for l in app.GetCalcRelevantObjects("*.ElmLod") if not l.outserv)
        
        error_code = ldf.Execute()
        results["status"] = "converged" if error_code == 0 else "diverged"
        results["error_code"] = error_code
        results["imbalance_before_mw"] = total_gen_mw - total_load_mw
        results["total_gen_mw"] = total_gen_mw
        results["total_load_mw"] = total_load_mw

    except Exception as e:
        results["error"] = str(e)
    
    results["pf_messages"] = []
    try:
        ow = app.GetOutputWindow()
        for i in range(min(50, ow.GetLineCount())):
            results["pf_messages"].append(ow.GetLine(i))
    except:
        pass
    
    with open("results/power_flow_slack.json", "w") as f:
        json.dump(results, f, indent=2)
```
