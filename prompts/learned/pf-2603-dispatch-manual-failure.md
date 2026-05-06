# [FALLIDO] Flujo de Potencia 2603 - Despacho Manual y Errores de API
Fecha: 2026-04-07
Tarea: "En el proyecto 2603, activar Base SEN, Laboral Diurno, desactivar ElmDsl, activar todos los generadores, realizar despacho al 103% de la carga y correr flujo."

## Qué se intentó
1. **Activación de Objetos**: Se intentó buscar y activar el `IntCase` "Base SEN" y el `IntScenario` "Laboral Diurno".
2. **Desactivación de DSL**: Se recorrieron todos los `ElmDsl` para ponerlos en `outserv=1` para evitar errores de DLL.
3. **Despacho Manual**: Se sumó la carga nominal (`plini`) y se intentó repartir la generación proporcionalmente entre todos los generadores, asignando un Slack manualmente.
4. **Ejecución de Flujo**: Se intentó configurar `ComLdf` con parámetros estándar y ejecutarlo.

## Por qué falló
1. **Atributos Inconsistentes**: El script falló repetidamente al intentar acceder a atributos como `sgn` en `ElmSym` (que estaba en el tipo, no en el objeto) o `iopt_init` en `ComLdf` (que parece no existir en esta versión de la base de datos/estudio).
2. **Estructura del Proyecto**: Los objetos `IntCase` e `IntScenario` no siempre se encuentran recursivamente con `GetContents` si el proyecto no está inicializado de cierta forma, lo que causó `IndexError`.
3. **Objeto OutputWindow**: El objeto devuelto por `app.GetOutputWindow()` no es iterable ni directamente serializable como JSON en esta versión de la API de Python 3.14/PF 2026, causando errores al intentar guardar los resultados.
4. **Divergencia Persistente**: Aunque se logró una ejecución técnica, el despacho manual "ciego" (reparto equitativo) en un sistema de gran escala como el SEN chileno (2603 buses) es propenso a causar divergencia masiva por desbalances locales de reactiva y tensiones fuera de rango.

## Recomendación
- **No Despachar Manualmente**: En bases operacionales (BD-OP), NO se debe modificar el despacho manualmente. Se debe confiar en la activación del escenario que ya trae el despacho de SCADA.
- **Validar Atributos**: Usar siempre `HasAttribute` antes de `Set/GetAttribute` y verificar si el atributo pertenece al elemento o a su tipo (`typ_id`).
- **Manejo de Mensajes**: Capturar `app.GetOutputWindow()` con cuidado; convertir a `str()` si es necesario, pero no intentar iterar sobre el objeto.
- **Uso de Scenarios**: Simplemente activar el escenario y correr el flujo sin tocar `pgini`, `usetp` o `ip_ctrl`.
