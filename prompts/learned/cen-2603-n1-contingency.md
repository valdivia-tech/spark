# Análisis de Contingencias N-1 — CEN 2603-BD-OP-COORD-DMAP
Fecha: 2026-04-11
Tarea: "Correr análisis N-1 sobre líneas de transmisión del SEN"

## Lecciones aprendidas

- **Filtrar elementos activos**: usar `outserv==0 AND m:u > 0.1` para barras. Barras con tensión 0 son áreas aisladas, no violaciones reales.
- **Banda de tensión**: usar 0.90-1.10 p.u. para transmisión. El rango 0.95-1.05 genera demasiadas violaciones falsas en distribución.
- **NO correr batches en paralelo** — PowerFactory no maneja concurrencia entre procesos.
- **Batches secuenciales**: para batches 220 kV (1,088 líneas), usar BATCH_START/BATCH_SIZE y referenciar la experiencia del batch anterior para reutilizar el script.
- **Formato de reporte**: Top 15 loaded + MW + kA es mucho más útil que solo reportar violaciones.
- **Validar con dos métodos de slack** (distribuido + único) para distinguir artefactos del solver de fenómenos reales.
- **Configuración base**: SIEMPRE correr el caso base primero (`ldf.Execute()`) antes del loop N-1. Usar la misma configuración de `cen-2603-power-flow.md` (iopt_pbal=4, iopt_init=1, iopt_errlf=1).

## Metodología

1. Configurar solver y correr caso base (ver `cen-2603-power-flow.md`)
2. Pre-colectar elementos a monitorear (líneas >= 110 kV, trafos >= 110 kV, barras >= 200 kV)
3. Loop: para cada línea de contingencia, poner `outserv=1`, correr ComLdf, capturar top loaded + voltajes, restaurar `outserv=0`
4. Reportar: convergencia, sobrecargas >100%, violaciones de tensión, delta de pérdidas

## Script template (500 kV)

El script completo está en `scripts/n1_500kv_rich.py` del repo don-nelson-2.0. Patrón clave:

```python
# Pre-collect monitoring elements (>= 110 kV)
monitor_lines = [line for line in app.GetCalcRelevantObjects("*.ElmLne")
                 if line.GetAttribute("outserv") == 0 and get_terminal_kv(line) >= 110]

# N-1 loop
for elem in contingency_lines:
    elem["obj"].outserv = 1       # disconnect
    rc = ldf.Execute()
    # ... capture top loaded, voltages, losses ...
    elem["obj"].outserv = 0       # restore

# Helper: get terminal kV
def get_terminal_kv(obj, bus_attr="bus1"):
    bus = obj.GetAttribute(bus_attr)
    if bus is None: return 0
    term = bus.GetParent()
    return term.GetAttribute("uknom") if term and term.HasAttribute("uknom") else 0
```

## Script template (220 kV batched)

Para 220 kV hay ~1,088 líneas. Usar batches con variables:
```python
BATCH_START = 0    # ajustar por batch
BATCH_SIZE = 200
BATCH_ID = "batch_1"
```

Script completo en `scripts/n1_220kv_batch.py`.

## Valores de referencia (Laboral Vespertino)

### 500 kV
- 34 contingencias, 34/34 convergieron
- Contingencia más costosa: Nva P.de.Azúcar - Polpaico (+19.4 MW pérdidas)
- Hallazgo crítico: Jadresic-Ibertaltal 1x500kV → TR RALCO N1 sube a 107.5%

### 220 kV
- 1,053 de 1,088 evaluadas, 1,050 convergieron, 3 divergieron
- 30 sobrecargas >100%
- TR RALCO N1 aparece en 17 contingencias (max 154.2%)
