# Modificar elemento y correr flujo de potencia
Fecha: 2026-03-24
Tarea: "en 7-bus.pfd, cambia la potencia del generador Red Externa a 10 MW, corre un flujo de potencia y muestra las tensiones de todas las barras"

## Lecciones aprendidas
- **Modificación de potencia en External Grid:** Para un objeto `ElmXnet`, el atributo para la potencia activa es `pgini`.
- **Búsqueda de elementos por nombre:** Es útil buscar en múltiples clases (`ElmXnet`, `ElmSym`) si no se está seguro del tipo exacto, filtrando por `loc_name`.
- **Uso de `GetCalcRelevantObjects`:** Es preferible a buscar en carpetas si se quieren los elementos que realmente participan en el cálculo.

## Script
```python
import sys, os, json
import powerfactory

# [Inicialización y carga de proyecto omitida por brevedad, ver load-flow-bus-voltages.md]

# Buscar "Red Externa" y cambiar potencia
external_grid = None
for cls in ["*.ElmXnet", "*.ElmSym"]:
    objs = app.GetCalcRelevantObjects(cls)
    for obj in objs:
        if "Red Externa" in obj.loc_name:
            external_grid = obj
            break
    if external_grid: break

if external_grid:
    external_grid.SetAttribute("pgini", 10.0)

# Correr flujo
ldf = app.GetFromStudyCase("ComLdf")
ldf.Execute()

# Extraer resultados
results = []
for bus in app.GetCalcRelevantObjects("*.ElmTerm"):
    if bus.HasAttribute("m:u"):
        results.append({
            "name": bus.loc_name,
            "v_pu": bus.GetAttribute("m:u")
        })
```
