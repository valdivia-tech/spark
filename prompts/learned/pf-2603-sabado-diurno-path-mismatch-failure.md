# [FALLIDO] Flujo de Potencia 'Sabado Diurno' en 2603 - Error de Inicialización y Rutas

Fecha: 2026-04-07
Tarea: "Activar Base SEN, Escenario Sabado Diurno en 2603-BD-OP-COORD-DMAP.pfd y correr flujo con configuración específica."

## Qué se intentó
- **Enfoque 1**: Uso de la ruta estándar de PowerFactory 2026 Preview. Falló porque el sistema tiene instalada la versión **2024 SP1**.
- **Enfoque 2**: Ajuste de rutas a 2024 SP1. Se produjeron errores persistentes de inicialización ("PowerFactory cannot be started again in the same process").
- **Enfoque 3**: Intento de detección automática de la aplicación usando `GetApplication()` y `GetApplicationExt()` con manejo de reintentos. El entorno bloqueó la inicialización tras múltiples intentos fallidos en el mismo proceso de Python.

## Por qué falló
- **Incompatibilidad de Versión**: Los scripts iniciales apuntaban a la versión 2026, mientras que el entorno real tiene la 2024 SP1.
- **Estado del Proceso**: Una vez que un intento de inicialización de la API de PowerFactory falla o se interrumpe, los intentos subsiguientes dentro del mismo proceso suelen devolver el error "PowerFactory cannot be started again in the same process", obligando a reiniciar el entorno.
- **Límite de Turnos**: Se alcanzó el límite de interacciones antes de poder verificar la ejecución con la ruta corregida (`C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12`).

## Recomendación
- Siempre verificar la existencia de las carpetas de versión en `C:\Program Files\DIgSILENT` antes de asumir una ruta de API.
- Si se cambia la ruta de la API (`sys.path`), es probable que se requiera un proceso de Python limpio. 
- Usar el patrón de caché de proyectos para evitar re-importaciones costosas que agotan el tiempo de ejecución.
