# [FALLIDO] Estabilización radical y limpieza topológica en 2512-bus
Fecha: 2026-04-06
Tarea: "Perform a final stabilization attempt with radical generation/load fix, 'ON_OFF' DPL scripts, and topological cleanup of isolated areas."

## Qué se intentó
- Activación de caso 'Base SEN 2030 Día', escenario 'ERV Maxima_Final_Dia_2030_ETF' y 3 variaciones.
- Ejecución de scripts DPL que contienen 'ON_OFF' en el nombre.
- Activación masiva (`outserv=0`) de todos los generadores y cargas.
- Despacho de generadores al 80% de su capacidad nominal (`sgnom` o `pnom`).
- Limpieza topológica: Identificar el área síncrona más grande usando el atributo `narea` de las barras y desactivar todo lo demás.
- Asignación de Slack a la red externa (`ElmXnet`) o generador síncrono más grande en el área principal.

## Por qué falló
- **Atributos inexistentes**: El atributo `narea` (área síncrona) no estaba poblado en los terminales (`ElmTerm`), incluso después de intentar ejecutar `ComNet` o un flujo de potencia. Esto causó que la lógica de limpieza desactivara TODO el sistema (40k+ elementos), resultando en 0 MW de potencia.
- **Fallas en ComNet**: El comando `Calculate Topology` (`ComNet`) falló al ejecutarse vía API (`RuntimeError: method call failed`), impidiendo el cálculo de islas.
- **Divergencia persistente**: El flujo de potencia AC divergió consistentemente incluso antes de la limpieza agresiva.
- **AttributeError**: Se descubrió que `DataObject` en PowerFactory 2026 no admite el acceso a atributos como `typ_id` mediante `GetAttribute()` si no están definidos explícitamente en la metadata del objeto, requiriendo el uso de `HasAttribute()` o `getattr()`.

## Recomendación
- No confiar en el atributo `narea` para limpieza topológica automatizada si el sistema no converge inicialmente; es mejor usar un generador de Slack (`ElmXnet`) y revisar manualmente las islas.
- Evitar el uso de `ComNet` en scripts de este proyecto, ya que parece inestable o requiere configuraciones previas no disponibles.
- El modelo '2512-bus' tiene una complejidad extrema (31,609 barras) y parece requerir una validación manual profunda en la interfaz gráfica para entender por qué las áreas síncronas no se calculan.
- Para obtener la capacidad (`sgnom`), usar siempre una función `safe_get` que verifique tanto el objeto como su tipo (`typ_id`).
```python
def get_capacity(obj):
    # sgnom para ElmSym, pnom para ElmGenstat
    attr = "sgnom" if obj.GetClassName() == "ElmSym" else "pnom"
    cap = obj.GetAttribute(attr) if obj.HasAttribute(attr) else 0.0
    if cap == 0:
        typ = obj.GetAttribute("typ_id") if obj.HasAttribute("typ_id") else None
        if typ:
            cap = typ.GetAttribute(attr) if typ.HasAttribute(attr) else 0.0
    return cap
```
