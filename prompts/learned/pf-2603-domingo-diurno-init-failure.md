# [FALLIDO] Power Flow Domingo Diurno 2603 - Error persistente de Inicialización API

Fecha: 2026-04-07
Tarea: "Correr flujo de potencia en escenario 'Domingo Diurno' del proyecto 2603-BD-OP-COORD-DMAP.pfd sin deshabilitar modelos ElmDsl."

## Qué se intentó
- **Limpieza de procesos**: Se ejecutó `taskkill` para eliminar instancias huérfanas de `powerfactory.exe`.
- **Configuración de Rutas**: Se verificó y configuró `sys.path` y `os.environ['PATH']` para apuntar a los binarios de **PowerFactory 2024 SP1** y Python 3.12.
- **Métodos de Inicialización**: 
    - `powerfactory.GetApplication()`
    - `powerfactory.GetApplicationExt()` con y sin argumentos.
    - `powerfactory.GetApplicationExt("", "", "/nodefault")`.
- **Diagnóstico de Entorno**: Verificación de existencia de archivos (`powerfactory.pyd`, `boost_python312...dll`) en la carpeta de la API.

## Por qué falló
- **Error 4002 / 7000**: La API devolvió consistentemente el código de error 4002 ("Application will be terminated"). 
- **Persistencia de Estado**: Una vez que el primer intento de inicialización falla dentro del proceso de Python, los intentos subsiguientes devuelven "PowerFactory cannot be started again in the same process".
- **Causa Raíz Probable**: El entorno de ejecución tiene una restricción de licencia o de configuración (posiblemente falta de acceso al servidor de licencias desde la sesión de la API) que impide que el motor se levante como proceso hijo. No es un error de código, sino de infraestructura/licenciamiento.

## Recomendación
- El entorno actual para la versión **2024 SP1** no está permitiendo conexiones vía API Python. 
- Se requiere una validación manual de la licencia en la estación de trabajo o el uso de una versión que tenga la licencia API habilitada (como la 2026 Preview mencionada en guías anteriores).
- No intentar más flujos de potencia en esta sesión de shell una vez detectado el error 4002, ya que el estado es irreversible para el proceso actual.
