# [FALLIDO] Topology and Dispatch Fix on 2512-bus Project
Fecha: 2025-05-22
Tarea: "Fix topology and dispatch on project 2512-bus.pfd: activate all, identify largest island, disconnect others, set slack, and dispatch."

## Qué se intentó
- **Búsqueda de islas con ComIsland**: Falló porque se trató como un objeto de datos sin método `Execute()` (aunque en PowerFactory los comandos se ejecutan así, hubo confusión con la API).
- **Búsqueda manual de islas (BFS)**: Inicialmente falló porque en este proyecto los atributos `bus1`/`bus2` de líneas y generadores no apuntan a `ElmTerm` sino a `StaCubic` (cubículos).
- **Manejo de Cubículos**: Se implementó una función `get_terminal` para subir en la jerarquía del objeto (`GetParent()`) hasta encontrar el `ElmTerm`.
- **Activación Masiva**: Se intentó activar todas las redes (`ElmNet`) y elementos (`outserv=0`).

## Por qué falló
- **Fragmentación Extrema**: A pesar de activar todo, el script reportó que cada terminal era una isla independiente (46,234 islas para 46,234 terminales). Esto indica que la conectividad a través de `StaCubic` o elementos de maniobra (interruptores/seccionadores) no fue capturada correctamente por el script.
- **Atributos inconsistentes**: El atributo `sgnom` (potencia nominal) no estaba presente en todos los objetos `ElmSym` o `ElmGenstat`, causando errores de ejecución tardíos.
- **Complejidad del Modelo**: Con 46k buses, cualquier error en la lógica de conectividad resulta en una red totalmente desconectada.

## Recomendación
- **Usar Topología Nativa**: En lugar de BFS manual, es imperativo hacer funcionar `ComIsland` o `ComLdf` con la opción de "rebuild topology" activa. 
- **Validación de Conectividad**: Antes de procesar islas, verificar la conectividad de un solo elemento (ej. una línea) imprimiendo sus terminales reales.
- **Interruptores**: Es probable que los `ElmSwitch` o cubículos necesiten ser cerrados explícitamente si `outserv=0` no es suficiente.
- **Acceso a Atributos**: Usar siempre un `safe_get` para evitar `AttributeError` en sistemas grandes donde los tipos de elementos son heterogéneos.
