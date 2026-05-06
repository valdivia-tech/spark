# [FALLIDO] Cortocircuito en línea en proyecto 7-bus
Fecha: 2026-05-04
Tarea: "Corregir el error de corrientes 0 kA en cortocircuitos de línea en 7-bus.pfd"

## Qué se intentó
- **Uso de EvtShc + ComShc (Complete):** Se creó un evento de falla al 50% en "Tramo 1". Aunque las tensiones de las barras cayeron (confirmando que la falla se aplicó), los atributos `m:Ikss:bus1` y `m:Ikss:bus2` en la línea reportaron 0.0 kA.
- **Uso de EvtShc + ComShc (IEC 60909):** Mismo resultado, corrientes en 0.0 kA.
- **Búsqueda exhaustiva de atributos:** Se iteraron todos los objetos relevantes buscando cualquier atributo `m:Ikss` o `m:I` que no fuera cero tras la falla. No se encontraron resultados en la línea ni en barras adyacentes.
- **Validación con falla en barra:** Se ejecutó un cortocircuito directo en la barra "S/E B 110 kV" (`shc.shcobj = bus`). Esto funcionó correctamente, reportando `Ikss = 1.398 kA`.

## Por qué falló
- En PowerFactory 2024 SP1, para el proyecto "7-bus", la ejecución de fallas mediante eventos (`EvtShc`) no parece popular los atributos de corriente estándar (`m:Ikss:bus1/2`) en el objeto `ElmLne`, a pesar de que el motor de cálculo procesa la falla (evidenciado por la caída de tensión).
- Se confirmó que el modelo tiene impedancia y fuentes (External Grid) ya que el fallo en barra sí entrega corrientes.
- El atributo `m:U` en las barras devuelve la tensión fase-neutro ($13.8/\sqrt{3} = 7.97$ kV), no la tensión entre fases.

## Recomendación
- No utilizar `EvtShc` para extraer corrientes de falla en este proyecto específico si se requiere automatización vía API.
- Si se necesita la corriente en una línea, realizar fallas en las barras de los extremos (0% y 100%) y usar esos valores como referencia, o verificar manualmente en la interfaz de PowerFactory qué objeto/capa de resultados está capturando la corriente del evento.
- Para tensiones de línea, multiplicar `m:U` por $\sqrt{3}$ o usar el atributo de tensión compuesta si está disponible.
