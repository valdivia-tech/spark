# Desconectar elemento y analizar tensiones bajas
Fecha: 2026-03-26
Tarea: "en 7-bus.pfd, desconecta el transformador TR2 y corre un flujo de potencia. Muestra qué barras quedaron con tensión menor a 0.95 pu"

## Lecciones aprendidas
- **Desconexión de elementos:** Se utiliza el atributo `outserv = 1` para sacar de servicio un elemento (transformador, línea, etc.).
- **Detección de islas:** Si al desconectar un elemento se aísla una parte de la red sin una referencia (slack) o generación, el flujo de potencia puede converger pero las barras aisladas mostrarán tensión 0.0 pu.
- **Filtrado de resultados:** Es eficiente iterar sobre `app.GetCalcRelevantObjects("*.ElmTerm")` y aplicar un condicional sobre el atributo `m:u` para identificar violaciones de límites de tensión.

## Script
```python
import sys, os, json
import powerfactory

# [Inicialización y carga de proyecto omitida, ver load-flow-bus-voltages.md]

# 1. Desconectar TR2
trafo_tr2 = None
for t in app.GetCalcRelevantObjects("*.ElmTr2"):
    if "TR2" in t.loc_name:
        trafo_tr2 = t
        break

if trafo_tr2:
    trafo_tr2.outserv = 1

# 2. Correr flujo de potencia
ldf = app.GetFromStudyCase("ComLdf")
ldf.Execute()

# 3. Identificar barras con tensión < 0.95 pu
low_v_buses = []
for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
    if bus.HasAttribute("m:u"):
        v_pu = bus.GetAttribute("m:u")
        if v_pu < 0.95:
            low_v_buses.append({
                "name": bus.loc_name,
                "v_pu": round(v_pu, 4)
            })

# Guardar resultados
with open("results/low_voltages.json", "w") as f:
    json.dump(low_v_buses, f, indent=2)
```
