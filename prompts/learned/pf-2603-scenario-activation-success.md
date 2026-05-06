# Flujo de potencia en 2603-BD-OP-COORD-DMAP con Activación de Escenario
Fecha: 2026-04-06
Tarea: "Activar el escenario 'Laboral Diurno' en el proyecto 2603, configurar un slack si falta y correr flujo de potencia."

## Lecciones aprendidas
- **Fragmentación de red**: El problema de las ~20,000 barras aisladas en este proyecto se resolvió activando el **Escenario de Operación** (`ElmScenario` o `IntScenario`) llamado 'Laboral Diurno'. Sin esto, la red permanece en un estado "fuera de servicio" masivo.
- **Detección de Escenarios**: Los escenarios pueden ser objetos de clase `ElmScenario` o `IntScenario`. Se recomienda buscar ambos tipos en todo el proyecto (`GetContents("*.ElmScenario", 1) + GetContents("*.IntScenario", 1)`).
- **Desbalance de Despacho**: Una vez activado el escenario, el sistema mostró una topología íntegra (solo 9 barras aisladas), pero divergió debido a un desbalance masivo de potencia (Generación: 4724 MW vs Carga: 8892 MW). 
- **Configuración de Slack**: Aunque se asigne la máquina más grande como slack, un desbalance de >4 GW suele ser inmanejable para un solo nodo de referencia en sistemas de este tamaño, causando divergencia inmediata.

## Script
```python
import sys, os, json, time
import powerfactory

# ... (inicialización estándar) ...

def run():
    app = powerfactory.GetApplication()
    proj = app.GetActiveProject()
    
    # 1. Activación de Escenario
    scenarios = proj.GetContents("*.ElmScenario", 1) + proj.GetContents("*.IntScenario", 1)
    for s in scenarios:
        if s.loc_name == "Laboral Diurno":
            s.Activate()
            break
            
    # 2. Activación de Caso de Estudio
    cases = proj.GetContents("*.IntCase", 1)
    for c in cases:
        if c.loc_name in ["Laboral Diurno", "Base SEN"]:
            c.Activate()
            break

    # 3. Verificación de Slack
    gens = app.GetCalcRelevantObjects("*.ElmSym")
    active_gens = [g for g in gens if g.outserv == 0]
    slack_found = any(g.ip_ctrl == 0 for g in active_gens)
    
    if not slack_found and active_gens:
        active_gens.sort(key=lambda g: g.gnm, reverse=True)
        active_gens[0].SetAttribute("ip_ctrl", 0) # 0=Slack
    
    # 4. Cálculo
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_net = 0 # AC
    ldf.iopt_init = 1 # Flat Start
    error_code = ldf.Execute()
```
