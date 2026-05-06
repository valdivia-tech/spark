# [FALLIDO] Modificar Shunt en 7-bus
Fecha: 2024-05-14
Tarea: "Write a PowerFactory Python script that modifies an ElmShnt: reactive_power_mvar (qcapn), n_steps (ncapx), n_steps_active (ncapa). Return previous and new values. Target system: 7-bus (.pfd)"

## Qué se intentó
- Se intentó localizar un `ElmShnt` en el proyecto `7-bus.pfd` usando `GetCalcRelevantObjects` y `GetContents` recursivo.
- Se descubrió mediante un inventario de elementos que el sistema `7-bus.pfd` (Taller 2) **no contiene elementos de tipo ElmShnt** de forma nativa.
- Se intentó crear un `ElmShnt` dinámicamente conectado a una barra para proceder con la modificación.
- Se intentó modificar los atributos `qcapn`, `ncapx` y `ncapa`.

## Por qué falló
- El atributo `qcapn` (potencia reactiva nominal) no se actualizó al valor asignado (`10.0`). Permaneció en un valor por defecto (~0.96).
- En PowerFactory, los elementos `ElmShnt` suelen requerir un tipo asociado (`TypShnt`) para definir sus características eléctricas. Al crear el elemento sin un tipo, el atributo `qcapn` parece comportarse como de solo lectura o estar vinculado a parámetros nominales no definidos (como `ushn` o la tensión de la barra).
- Se agotó el presupuesto de turnos intentando diagnosticar por qué los atributos no persistían.

## Recomendación
- Antes de modificar shunts en modelos desconocidos, verificar si existen o si requieren un `TypShnt`.
- Para el caso del `7-bus.pfd`, si se requiere un shunt, es necesario crear tanto el `ElmShnt` como su `TypShnt` correspondiente, o asignar valores a `ushn` y otros parámetros básicos antes de intentar fijar la potencia `qcapn`.
- Validar siempre si el elemento existe antes de proceder; si no existe, informar al usuario en lugar de intentar crearlo dinámicamente a menos que se solicite explícitamente.
