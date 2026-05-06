# [FALLIDO] Power Flow 'ERNC CC' en Proyecto 2603 - Error de Inicialización API

Fecha: 2026-04-07
Tarea: "Abrir proyecto 2603-BD-OP-COORD-DMAP, activar Base SEN y ERNC CC, correr flujo con slack distribuido y reportar balance por tecnología (~8098 MW)."

## Qué se intentó
- **Inicialización Estándar**: Se intentó `GetApplication()` y `GetApplicationExt()` usando la ruta de PowerFactory 2024 SP1 (Python 3.12).
- **Depuración de Instancia**: Se verificó que `GetApplication()` devolvía `None` en lugar de una excepción o el objeto, indicando un estado inconsistente del motor.
- **Error 4002**: `GetApplicationExt()` falló repetidamente con el código 4002, que suele estar asociado a problemas de licencia o a que el motor ya está en uso/bloqueado.
- **Reinicio de Proceso**: Se intentó `taskkill` sobre `PowerFactory.exe`, pero el proceso no estaba en ejecución, lo que sugiere que el fallo ocurre antes de que el ejecutable principal se levante completamente.

## Por qué falló
- **Inconsistencia del Motor**: El mensaje "PowerFactory cannot be started again in the same process" sugiere que el entorno de Python retuvo rastros de una inicialización fallida anterior, bloqueando intentos subsiguientes.
- **Falla de GetApplication**: El hecho de que `GetApplication()` retorne `None` sin lanzar una excepción impide el acceso a `app.GetCurrentUser()`, bloqueando toda la lógica del script.

## Recomendación
- El entorno de ejecución requiere un reinicio completo para liberar las librerías de PowerFactory.
- Validar si la licencia de PowerFactory 2024 SP1 está disponible y configurada correctamente en el servidor.
- Considerar el uso de una versión de Python que coincida exactamente con la requerida por la instalación local (3.12).
