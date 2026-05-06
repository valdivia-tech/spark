# [FALLIDO] Inicialización API PowerFactory 2024 SP1 en Proyecto 7-bus

Fecha: 2026-04-07
Tarea: "Corre un flujo de potencia en 7-bus.pfd para verificar el estado de la API. Solo quiero saber si converge."

## Qué se intentó
- **Aproximación 1**: Inicialización estándar usando `sys.path` y `os.environ['PATH']` apuntando a la versión detectada en disco: `C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12`.
- **Aproximación 2**: Uso de `GetApplicationExt()` y `GetApplication()` de forma secuencial.
- **Aproximación 3**: Verificación de procesos activos (`tasklist`) para asegurar que no hubiera instancias huérfanas bloqueando el puerto de la API.

## Por qué falló
- **Error 4002**: Al llamar a `powerfactory.GetApplicationExt()`, el motor devolvió el error 4002. Este error indica que la aplicación no pudo iniciarse, usualmente debido a:
    1. Falta de una licencia válida disponible para la API.
    2. Incompatibilidad entre el entorno de ejecución (Python 3.12) y los binarios de la versión 2024 SP1 instalada.
    3. Restricciones del sistema que impiden al proceso de Python levantar el proceso hijo de PowerFactory.
- **Mensaje Crítico**: Se observó el mensaje "PowerFactory cannot be started again in the same process", lo que sugiere que la DLL de la API detecta un estado de inicialización fallido persistente dentro de la misma sesión de shell.

## Recomendación
- El entorno actual con la versión **2024 SP1** parece tener problemas de licencia o configuración que impiden el uso de la API Python. 
- Se debe verificar si existe una instalación de la versión **2026 Preview** (mencionada en la documentación) o si la licencia de la 2024 permite acceso externo.
- Probar la ejecución manual de PowerFactory en el escritorio remoto para descartar problemas de servidor de licencias.
