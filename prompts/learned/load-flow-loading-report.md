# Flujo de potencia y reporte de carga de ramas
Fecha: 2026-03-24
Tarea: "en 7-bus.pfd, lista todas las líneas y transformadores del sistema con su carga porcentual después de un flujo de potencia"

## Lecciones aprendidas
- **Atributos de carga:** Tanto para líneas (`ElmLne`) como para transformadores de 2 devanados (`ElmTr2`), el atributo de carga porcentual es `c:loading`.
- **Búsqueda de objetos:** Usar `app.GetCalcRelevantObjects("*.ElmLne")` y `app.GetCalcRelevantObjects("*.ElmTr2")` asegura que solo se procesen elementos que participan en el cálculo actual.
- **Manejo de resultados:** Es útil capturar también potencias activas y reactivas (`m:P:bus1`, `m:Q:bus1`) para dar contexto a la carga, aunque no se pida explícitamente, ya que ayuda a verificar la dirección del flujo.

## Script
```python
import sys, os, json
import powerfactory

# Inicialización omitida para brevedad, ver patrones base

# ... carga de proyecto y ejecución de ComLdf ...

output = {
    "lines": [],
    "transformers": []
}

if error_code == 0:
    # Líneas
    for line in app.GetCalcRelevantObjects("*.ElmLne"):
        if line.HasAttribute("c:loading"):
            output["lines"].append({
                "name": line.loc_name,
                "loading_pct": line.GetAttribute("c:loading"),
                "p_mw": line.GetAttribute("m:P:bus1"),
                "q_mvar": line.GetAttribute("m:Q:bus1")
            })
    
    # Transformadores
    for trafo in app.GetCalcRelevantObjects("*.ElmTr2"):
        if trafo.HasAttribute("c:loading"):
            output["transformers"].append({
                "name": trafo.loc_name,
                "loading_pct": trafo.GetAttribute("c:loading")
            })

with open("results/loading_report.json", "w") as f:
    json.dump(output, f, indent=2)
```
