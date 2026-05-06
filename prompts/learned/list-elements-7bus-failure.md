# [FALLIDO] Listar elementos en 7-bus.pfd (Bloqueado por Error 4002)
Fecha: 2026-05-18
Tarea: "list all elements of a given type (generator, load, line, transformer, bus) for 7-bus (.pfd at projects/7-bus.pfd)"

## Qué se intentó
- Inicialización estándar de PowerFactory 2024 SP1 usando `GetApplicationExt()`.
- Múltiples variaciones de `sys.path` y variables de entorno (`PATH`).
- Uso de patrones de inicialización probados en experiencias previas (`7-bus-power-flow.md`, `7-bus-balanced-pf-2024.md`).
- Verificación de la existencia del archivo `.pfd` en `../projects/7-bus.pfd`.

## Por qué falló
- El script falla consistentemente con `powerfactory.ExitError: Exit with error code 4002` durante la llamada a `GetApplicationExt()`.
- Este es un error de infraestructura global (falla de inicialización del motor o servidor de licencias no disponible), no un error del script o del modelo.
- Se confirmó que el servidor de licencias configurado en `PowerFactory.ini` es `10.2.36.213`.

## Recomendación
- Escalar el error 4002 al administrador de la infraestructura.
- No reintentar scripts en este entorno hasta que se resuelva la comunicación con el servidor de licencias.
