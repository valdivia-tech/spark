# [FALLIDO] Flujo de Potencia 'ERNC CC' en Proyecto 2603 - Falla de Inicialización

Fecha: 2026-04-07
Tarea: "Activa el proyecto 2603-BD-OP-COORD-DMAP.pfd, activa el Study Case 'Base SEN' y el escenario 'ERNC CC', y ejecuta un flujo de potencia con slack distribuido."

## Qué se intentó
- **Intento 1-2**: Uso de rutas de PowerFactory 2026 (Preview) y Python 3.14. Falló porque no existen en el entorno.
- **Intento 3-4**: Identificación de la ruta correcta del entorno (`C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12`). Se intentó `GetApplicationExt()` y `GetApplication()`.
- **Intento 5-6**: Error persistente `powerfactory.ExitError: Exit with error code 4002`. Este error suele indicar que la aplicación no puede abrirse debido a una sesión ya abierta o problemas de licencia/inicialización.
- **Intento 7-10**: Re-intentos de inicialización con diferentes flags (`None, None`) y limpieza de entorno. Se recibió el mensaje "PowerFactory cannot be started again in the same process", indicando que el motor de Python mantenía una referencia o el proceso quedó en estado inconsistente.

## Por qué falló
- **Causa Raíz**: El entorno de ejecución presenta una incompatibilidad o bloqueo persistente con la API de PowerFactory 2024 SP1. A pesar de usar los paths correctos para Python 3.12, la llamada a `GetApplicationExt()` falló sistemáticamente con el código 4002.
- **Bloqueo de Proceso**: Los intentos repetidos en el mismo entorno de shell resultaron en errores de "proceso ya iniciado", impidiendo una recuperación limpia sin reiniciar el worker.

## Recomendación
- Verificar la integridad de la instalación de PowerFactory 2024 SP1 en el servidor de ejecución.
- Asegurarse de que no existan procesos `powerfactory.exe` huérfanos antes de iniciar el script.
- Utilizar un script de prueba de conexión minimalista antes de intentar la lógica de negocio pesada para ahorrar turnos.
