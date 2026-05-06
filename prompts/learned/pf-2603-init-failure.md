# [FALLIDO] Inicialización API PowerFactory 2024 SP1 en Proyecto 2603
Fecha: 2026-04-07
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: Activar 'Base SEN', 'Domingo Madrugada', correr flujo con slack distribuido y extraer balance tecnológico."

## Qué se intentó
- **Enfoque 1**: Uso de la ruta estándar para PowerFactory 2026 Preview. Resultó en error de inicialización (4002).
- **Enfoque 2**: Detección de versión mediante `dir`. Se encontró que la versión instalada es **PowerFactory 2024 SP1** en `C:\Program Files\DIgSILENT\PowerFactory 2024 SP1`.
- **Enfoque 3**: Intento de inicialización usando `GetApplicationExt()` con la ruta de 2024 SP1 y Python 3.12. Persistió el error 4002 y ocasionalmente 7000.

## Por qué falló
- **Falla de Inicialización (Error 4002)**: El motor de PowerFactory no pudo arrancar en el entorno actual a pesar de configurar correctamente `sys.path` y la variable de entorno `PATH`. 
- **Inconsistencia de Entorno**: Aunque la ruta al ejecutable y DLLs de PowerFactory existe, el objeto aplicación (`app`) no pudo ser instanciado, impidiendo cualquier interacción con el proyecto o los casos de estudio.

## Recomendación
- Antes de ejecutar scripts complejos, verificar la salud del motor de PowerFactory con un script de diagnóstico mínimo.
- Si el error 4002 persiste, puede deberse a un conflicto de licencias o a que el proceso anterior no se cerró correctamente (aunque se intentó usar `GetApplication` como respaldo).
- Validar la ruta exacta de la instalación de PowerFactory en el servidor de ejecución antes de codificar rutas fijas.
