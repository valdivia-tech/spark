# Cortocircuito en línea al 30%
Fecha: 2026-03-26
Tarea: "en 7-bus.pfd, haz un cortocircuito trifásico en la Linea 2 al 30% y muestra las corrientes de falla"

## Lecciones aprendidas
- **Eventos para fallas en línea.** Para realizar un cortocircuito en una ubicación intermedia de una línea (0-100%), se debe crear un objeto `EvtShc` en el caso de estudio activo.
- **Configuración del evento.** Se asigna `evt.p_target = linea`, `evt.i_p_target = 30.0` y `evt.i_shc = 0` (para 3-fases).
- **Método "Complete" (iopt_mde=1).** En este entorno, el método "Complete" funcionó mejor que el IEC 60909 para procesar eventos de cortocircuito en líneas. Se recomienda correr un flujo de potencia (`ComLdf`) antes del cortocircuito cuando se usa el método "Complete".
- **Lectura de resultados.** Las corrientes de contribución se obtienen de los atributos `m:Ikss:bus1` y `m:Ikss:bus2` del objeto de la línea (`ElmLne`). La corriente de falla total es la suma de estas contribuciones.
- **Limpieza de eventos.** Siempre borrar el objeto `EvtShc` después de la ejecución para evitar interferencias en cálculos posteriores.

## Script
```python
import sys, os, json
import powerfactory

# Initialization
pf_path = os.environ.get("POWERFACTORY_PATH", r"C:\Program Files\DIgSILENT\PowerFactory 2026 Preview\Python\3.14")
if pf_path not in sys.path:
    sys.path.insert(0, pf_path)
pf_root = os.path.dirname(os.path.dirname(pf_path))
os.environ['PATH'] = pf_root + os.pathsep + os.environ.get('PATH', '')

app = powerfactory.GetApplicationExt(None, None)
user = app.GetCurrentUser()

# Load project (cache pattern)
# ... activation logic ...

# Find Linea 2
linea2 = [l for l in app.GetCalcRelevantObjects("*.ElmLne") if "Linea 2" in l.loc_name][0]

# Pre-calculation: Load Flow
app.GetFromStudyCase("ComLdf").Execute()

# Setup Fault Event
study_case = app.GetActiveStudyCase()
evt = study_case.CreateObject("EvtShc", "LineFault")
evt.p_target = linea2
evt.i_p_target = 30.0  # 30% from Bus 1
evt.i_shc = 0          # 3-phase

# Run Short Circuit (Complete method)
shc = app.GetFromStudyCase("ComShc")
shc.iopt_mde = 1       # Complete
shc.iopt_shc = "3PSC"
shc.Execute()

# Results
ik1 = linea2.GetAttribute("m:Ikss:bus1")
ik2 = linea2.GetAttribute("m:Ikss:bus2")
total_ik = ik1 + ik2

# Cleanup
evt.Delete()
```
