# [FALLIDO] Flujo de potencia en 2603-BD-OP-COORD-DMAP con Slack Robusto y Redespacho
Fecha: 2026-04-06
Tarea: "Activar Laboral Diurno, duplicar pgini de generadores, crear slack robusto si no existe y correr flujo de potencia."

## Qué se intentó
- Se activó el caso de estudio 'Base SEN' y el escenario de operación 'Laboral Diurno'.
- Se activaron manualmente todos los objetos `ElmNet` (Grids) y `IntScheme` (Variations) del proyecto.
- Se duplicó el despacho `pgini` de todos los generadores activos (`ElmSym` y `ElmGenstat`), resultando en un total de 9448.83 MW (partiendo de ~4724 MW).
- Se identificó que no había `ElmXnet` (Red Externa) activa. Se creó una de forma temporal en la barra 'LOS CHANGOS 500 kV B1' (elegida por nivel de tensión y conectividad) para actuar como Slack.
- Se ejecutó el flujo de potencia con "Flat Start" y "Disconnect Isolated Nodes".

## Por qué falló
- **Divergencia inmediata (error_code=1)**. 
- A pesar de tener un Slack definido y un despacho manual, el sistema detectó **20,368 barras aisladas**.
- El desbalance inicial (antes de resolver) era de ~556 MW (Generación: 9448 MW vs Carga: 8892 MW), lo cual es manejable para un Slack, pero la fragmentación masiva de la red impide la convergencia. 
- La activación masiva de Grids y Variaciones no fue suficiente para establecer una topología coherente.

## Recomendación
- El proyecto 2603 parece tener una estructura de datos donde el escenario 'Laboral Diurno' requiere una combinación muy específica de Variaciones o Scripts DPL de preparación que no están activos por defecto. 
- Se requiere una inspección manual de la topología para entender por qué tantas barras permanecen aisladas.

## Script
```python
import sys, os, time, json
import powerfactory

def run():
    app = powerfactory.GetApplication()
    user = app.GetCurrentUser()
    # (Código de carga de proyecto y activación omitido para brevedad, ver logs anteriores)
    
    # Redespacho
    gens = app.GetCalcRelevantObjects("*.ElmSym") + app.GetCalcRelevantObjects("*.ElmGenstat")
    for g in gens:
        if g.outserv == 0:
            g.SetAttribute("pgini", g.GetAttribute("pgini") * 2.0)
            
    # Slack Robusto
    xnets = app.GetCalcRelevantObjects("*.ElmXnet")
    if not xnets:
        buses = app.GetCalcRelevantObjects("*.ElmTerm")
        # Selección de barra más "fuerte"
        best_bus = sorted(buses, key=lambda b: b.uknom*100 + len(b.GetConnectedElements()), reverse=True)[0]
        slack = best_bus.GetParent().CreateObject("ElmXnet", "TempSlack")
        slack.bus1 = best_bus
        slack.i_P_mode = 0 # Slack
    
    # Flujo
    ldf = app.GetFromStudyCase("ComLdf")
    ldf.iopt_init = 1 # Flat Start
    ldf.iopt_net = 1  # Disconnect isolated
    error_code = ldf.Execute()
```
