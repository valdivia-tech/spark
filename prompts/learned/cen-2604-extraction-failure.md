# [FALLIDO] Flujo de potencia y extracción por zonas en BD 2604
Fecha: 2026-05-22
Tarea: "Ejecutar flujo de potencia para 10 escenarios en 2604-BD-OP-COORD-DMAP.pfd y extraer carga de trafos y generación por zona/tecnología."

## Qué se intentó
- **Activación de Escenarios**: En este proyecto, los escenarios (IntScenario) están en la raíz del proyecto, no dentro del Study Case. Se debe activar el Study Case "Base SEN" primero y luego el escenario por nombre.
- **Extracción de Resultados**: Se intentó usar `m:P:bus1` para generadores y `m:loading` para transformadores.
- **Configuración LDF**: Se usó la receta validada `iopt_pbal=4, iopt_init=1, iopt_errlf=1`.

## Por qué falló
- **Inconsistencia de Atributos**: A diferencia de la BD 2603, en la BD 2604 los generadores (`ElmSym`, `ElmGenstat`) no devolvieron valores válidos para `m:P:bus1` (el atributo reportaba no existir o devolvía 0.0 a pesar de una ejecución exitosa del flujo).
- **Atributos Dinámicos**: Se intentó buscar alternativas (`m:Psum`, `m:Pgen`, `c:pgini`), pero no se logró encontrar el mapeo correcto de resultados de potencia activa en el tiempo disponible.
- **Límite de turnos**: Se agotaron los intentos tratando de depurar la extracción de resultados de generación sin éxito.

## Recomendación
- Realizar una inspección manual en PowerFactory de un generador despachado después de correr el flujo para identificar el nombre exacto de la variable de resultado de potencia activa (P) en esta versión de la base de datos.
- Verificar si los resultados están en un objeto de resultados (`ElmRes`) separado en lugar de estar integrados en los elementos.
- La receta de convergencia de la 2603 funciona para que el flujo termine, pero la extracción de datos requiere validación de atributos específicos para la 2604.
