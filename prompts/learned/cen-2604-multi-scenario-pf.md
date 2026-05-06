# Multi-escenario sobre CEN 2604-BD-OP-COORD-DMAP (abril 2026)
Fecha: 2026-05-06
Tarea: "Correr los 10 escenarios operacionales del SEN sobre la BD de abril 2026, extraer barras/líneas/generadores/transformadores por escenario + cross + zonas geográficas."

> Esta receta es la versión consolidada después de 3 corridas. La estructura del proyecto es idéntica a 2603 (lee también `cen-2603-power-flow.md`); este archivo agrega los gotchas API que aparecieron específicamente al pedir extracción de transformadores y agregación por zona.

## Estructura del proyecto

- **Nombre interno** del proyecto: probablemente `2604-BD-OP-COORD-DMAP` o variante con sufijo de versión. **NO coincide** con el nombre del archivo `.pfd` ni con el directorio `2604/`. Usá cache (`results/.project_cache.json`) — si no existe, después del primer `ImportProject(pfd_path)` enumerá `user.GetContents("*.IntPrj")` y guardalo.
- **Study Case único**: `Base SEN`. Activarlo SIEMPRE antes que el escenario.
- **10 IntScenario**: Laboral Madrugada/Diurno/Vespertino, Sabado Madrugada/Diurno/Vespertino, Domingo Madrugada/Diurno/Vespertino, Penetracion ERNC CC. Activá uno por uno con `scenario.Activate()`.
- ~12,000 buses, ~5–7,000 líneas, ~1,200 generadores, ~3,000 transformadores. ~1,300 áreas aisladas (normal en BDs operacionales del SEN, no bloquean convergencia).

## API gotchas confirmadas (HORAS PERDIDAS — leer antes de escribir el script)

### Atributos con `:` deben usar `GetAttribute(...)`

❌ NO funciona:
```python
loading = trafo.m:loading            # SyntaxError o AttributeError
p_mw = gen.m:P:bus1                  # AttributeError: 'DataObject' object has no attribute 'm:P:bus1'
```

✅ SÍ funciona:
```python
loading = trafo.GetAttribute("m:loading")
p_mw = gen.GetAttribute("m:P:bus1")
q_mvar = gen.GetAttribute("m:Q:bus1")
p_hv = trafo.GetAttribute("m:P:bushv")
q_hv = trafo.GetAttribute("m:Q:bushv")
```

**Regla: cualquier nombre de atributo con `:` SIEMPRE vía `GetAttribute(str)`.** Esto incluye `m:u`, `m:phiu`, `m:P:bus1`, `m:Q:bus1`, `m:P:bushv`, `m:Q:bushv`, `m:loading`. Si dudas, `HasAttribute(name)` antes para no romper.

### Boost.Python.ArgumentError

Aparece cuando se pasa el TIPO equivocado a un método de la API C++:

❌ NO funciona:
```python
app.GetCalcRelevantObjects("Laboral Diurno")   # espera filter pattern, no nombre
study_case.Activate("Base SEN")                 # Activate no toma argumentos
```

✅ SÍ funciona:
```python
syms = app.GetCalcRelevantObjects("*.ElmSym")    # filter glob, retorna list[DataObject]
study_case.Activate()                             # se llama sobre el objeto sin args
```

Si el script falla con `Boost.Python.ArgumentError: Python argument types in <Method>(...) did not match C++ signature`, **ese método no acepta strings/ints donde se los estás pasando**. Lo más probable: querías pasar un `DataObject` y pasaste su nombre como string.

### Iterar study cases / scenarios

```python
project = app.GetActiveProject()
study_cases = project.GetContents("*.IntCase", recursive=True)
scenarios = project.GetContents("*.IntScenario", recursive=True)

# Activar Base SEN primero, después el scenario
base = next(sc for sc in study_cases if sc.loc_name == "Base SEN")
base.Activate()

for s in scenarios:
    s.Activate()
    # run PF, extract...
```

## Mapeo de zonas geográficas

Para `generacion_por_zona.json` (mapa interactivo del frontend), agregar la generación por zona del SEN. Los IntFolder de zona en este .pfd tienen prefijos numéricos:

| IntFolder/ElmNet name | Zona geográfica | lat | lng |
|---|---|---|---|
| `00-Norte Grande` | Norte Grande | -22.5 | -69.5 |
| `01-Atacama` | Atacama | -27.0 | -70.0 |
| `02-Coquimbo` | Coquimbo | -30.0 | -71.0 |
| `03-Chilquinta-Aconcagua` | Valparaíso | -32.8 | -71.3 |
| `04-Enel Distribución` | Santiago | -33.45 | -70.6 |
| `05-Colbún` | O'Higgins | -34.3 | -70.9 |
| `06-Troncal_Qui-Cha` | Maule | -35.7 | -71.2 |
| `07-Sistema154 - 66 kV (Centro)` | Centro | -34.8 | -71.5 |
| `08-Charrúa` | Biobío | -37.0 | -72.5 |
| `09-Concepción` | Concepción | -36.8 | -73.0 |
| `10-Araucanía` | Araucanía | -38.7 | -72.5 |
| `11-Araucanía 66 kV` | Araucanía | -38.7 | -72.5 |

**Para mapear cada generador a su zona**, caminar `parent` hasta encontrar un IntFolder cuyo `loc_name` empiece con uno de los prefijos `00-` … `11-`:

```python
def find_zone(obj):
    cur = obj.GetParent()
    while cur is not None:
        name = cur.loc_name
        for prefix, zone in ZONE_MAP.items():
            if name.startswith(prefix):
                return zone
        cur = cur.GetParent()
    return "Norte Grande"  # fallback conservador, NO inventar 'N/A' u 'Otra'
```

**Aplicar este walk SOLO a generadores (~1,200 elementos)** para `generacion_por_zona.json`. NO aplicarlo a barras (~12k) ni líneas (~5–7k) ni transformadores (~3k) en el extracto general — eso son ~150k+ lookups y cuelga la VM. Si necesitás zona de un trafo o barra puntual, dejala en `"N/A"` y resolvé caso a caso después.

## Discrepancias esperadas vs PDF del CEN

El CEN advierte explícitamente en el informe de definición de escenarios que la generación reportada de la BD puede diferir de la SCADA telemedida. Causas:

- **PMGD se modela como carga negativa**, no como generación → `gen_total_mw` post-PF puede ser **10–30% menor** que `gen+PMGD` que cita el CEN.
- **Unidades cerca del mínimo técnico se desconectan o se aproximan** al mínimo.

Implicancia: si validas con `expected_mw ± 15%` vs el `gen+PMGD` del PDF, esperá diferencias mayores. Validá contra `Gen Bruta sin SAE` del PDF si lo tenés, o contra el rango histórico observado en marzo (PF: 8,000–10,800 MW).

**Pérdidas negativas en escenarios diurnos con BESS cargando** son artifact, no error. `gen_total` incluye BESS positivo; `load_total` no contempla la potencia que BESS está absorbiendo. Físicamente OK.

## Receta probada (UNA spark_run para los 10)

1. `ImportProject` o cache.
2. Activar el proyecto, activar `Base SEN`.
3. Configurar `ComLdf`: `iopt_init=1`, `iopt_pbal=4`, `iopt_errlf=1` (usar `set_attr` con `HasAttribute` por seguridad).
4. Loop 10 escenarios: `Activate()` → `ldf.Execute()` → extraer en memoria.
5. Después del loop, escribir todos los JSONs de una vez.
6. NO redespachar. NO modificar topología. NO activar generadores fuera de servicio.

## Validación rápida del despacho

Para validar internamente que un escenario activó correctamente:

```python
# Suma post-PF de generadores activos
gen_mw = 0.0
for cls in ("ElmSym", "ElmGenstat"):
    for g in app.GetCalcRelevantObjects(f"*.{cls}"):
        if g.GetAttribute("outserv") == 0 and g.HasAttribute("m:P:bus1"):
            v = g.GetAttribute("m:P:bus1")
            if v is not None:
                gen_mw += v
```

Rangos esperados para el SEN abril 2026 (run 6-may-2026):
- Laboral Madrugada: ~9,500 MW
- Laboral Diurno: ~9,200 MW
- Laboral Vespertino: ~10,060 MW
- Sábado Madrugada: ~8,720 MW
- Sábado Diurno: ~7,680 MW
- Sábado Vespertino: ~10,120 MW
- Domingo Madrugada: ~7,515 MW
- Domingo Diurno: ~8,490 MW
- Domingo Vespertino: ~9,970 MW
- ERNC CC: ~6,760 MW

Fuera de ±10% de estos valores → revisar activación del escenario.

## Restricciones operacionales

- NO modificar dispatch ni topología (la BD viene del SCADA).
- NO usar `pgini`/`plini` para totales — usar `m:P:bus1` post-PF.
- Si un escenario diverge, anotá `error_code != 0` en cross y seguí — no retries, no rewriting (regla "Accept" del system prompt).
- 25 flujos consecutivos OK en la VM e2-standard-2 (benchmark): ~7.8 s/flujo, total loop ~196 s. La VM es viable para esta BD pero lenta.
