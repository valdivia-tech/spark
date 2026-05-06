# [FALLIDO] Inicialización de PowerFactory 2024 SP1 en Proyecto 2603

Fecha: 2026-04-07
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd (Escenario: Domingo Madrugada): 1. Intenta inicializar PowerFactory usando la versión 2024 SP1... 2. Activa Study Case 'Base SEN' e IntScenario 'Domingo Madrugada'... 3. Ejecuta flujo con iopt_pbal=4, iopt_init=1, iopt_errlf=1."

## Qué se intentó
- **Aproximación 1**: Configuración de `sys.path` y `os.environ['PATH']` apuntando a `C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12` (coincidiendo con la versión de Python del sistema). Uso de `GetApplicationExt()`.
- **Aproximación 2**: Intento de inicialización robusta probando `GetApplication()` y `GetApplicationExt()` secuencialmente.
- **Aproximación 3**: Verificación de rutas de DLLs (agregando el directorio raíz de PowerFactory al PATH de Windows).

## Por qué falló
- **Error de Inicialización (4002)**: El motor de PowerFactory 2024 SP1 falló consistentemente al iniciar, devolviendo `None` o el código de error 4002.
- **Causa Raíz Probable**: El error 4002 típicamente indica problemas con la licencia o la configuración de la instalación de PowerFactory que impiden que la API tome el control del motor en el entorno actual.

## Recomendación
- Validar la disponibilidad de licencias para la versión 2024 SP1 en el servidor.
- Considerar el uso de la versión "2026 Preview" si está disponible, ya que ha mostrado mayor estabilidad en tareas previas.
- Si es estrictamente necesaria la 2024 SP1, realizar una prueba manual de apertura de la aplicación en el entorno antes de reintentar vía API.
