# [FALLIDO] Cortocircuito en línea al 50%
Fecha: 2025-05-15
Tarea: "en 7-bus.pfd, haz un cortocircuito trifásico en la Linea 1 al 50% de su longitud y muestra las corrientes de falla en todas las barras"

## Qué se intentó
- **Enfoque 1:** Crear un evento de falla (`EvtShc`) dentro del caso de estudio, configurando `p_target` como la línea y `i_p_target = 50`. Luego ejecutar `ComShc` con el método IEC 60909 (`iopt_mde=0`).
- **Error:** El comando `ComShc.Execute()` retornó `1` (error), indicando que el cálculo no se pudo realizar.
- **Exploración de atributos:** Se verificó si `ComShc` tenía atributos directos para ubicación en línea (`f_shcloc`, `shcloc`), pero `HasAttribute` retornó `0` para estos en este entorno.

## Por qué falló
- **Incompatibilidad de IEC 60909 con Eventos:** El método IEC 60909 en PowerFactory suele estar diseñado para fallas en nodos específicos (`shcobj`). Aunque la interfaz gráfica permite fallas en líneas, la ejecución vía script de un `EvtShc` junto con `ComShc` puede requerir que el método de cálculo sea "Complete" (`iopt_mde=1`) o que existan banderas adicionales para procesar eventos que no fueron detectadas.
- **Configuración del objeto `ComShc`:** Al no encontrar atributos de distancia/ubicación directamente en el objeto de comando, se dependió del objeto `EvtShc`, el cual no fue procesado correctamente por el motor de cálculo en la configuración utilizada.

## Recomendación
- Intentar usar el método "Complete" (`iopt_mde=1`) desde el inicio si se usan eventos.
- Si se requiere IEC 60909, verificar si la versión de PowerFactory permite asignar la línea directamente a `shcobj` y si existen atributos ocultos (usar `GetAttributes()` si está disponible en la versión, aunque en este entorno se usa `HasAttribute` para seguridad).
- Alternativa manual: Dividir la línea en dos en el modelo original para crear un nodo intermedio al 50%, lo cual permite usar el método de falla en barra estándar.
