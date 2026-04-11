# [FALLIDO] Error Global de Inicialización (Error 4002/7000)
Fecha: 2026-04-10
Tarea: "Cualquier tarea — PowerFactory no inicia"

## Qué se intentó

- Ejecutar `powerfactory.GetApplication()` y `GetApplicationExt()` — retorna `None` o falla con código 7000.
- Ajustar `sys.path` a carpetas Python 3.12 y 3.8 — no resuelve.
- Configurar variables de entorno `POWERFACTORY_PATH` — no resuelve.
- Probar con proyecto diferente (7-bus.pfd vs 2603-BD-OP-COORD-DMAP) — mismo error.

## Por qué falló

- El error **4002** (o código de salida **7000**) es un fallo catastrófico de inicialización del motor PowerFactory 2024 SP1.
- Ocurre durante `GetApplication()` **antes** de cargar cualquier proyecto.
- Es un problema **global de infraestructura** (licencias o instalación), no del proyecto ni del script.
- Una vez que ocurre en una sesión, los intentos subsiguientes fallan con "PowerFactory cannot be started again in the same process".

## Recomendación

1. NO reintentar más de 2 veces.
2. Verificar estado del servidor de licencias.
3. NO intentar solucionar con cambios en el script, el proyecto, o deshabilitando ElmDsl.
4. Reportar el error al administrador del servidor de ejecución.
