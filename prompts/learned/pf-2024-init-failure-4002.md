# [FALLIDO] Inicialización API PowerFactory 2024 SP1 - Error 4002/7000

Fecha: 2026-04-07
Tarea: "Prueba rápida de inicialización y flujo de potencia en proyecto pequeño."

## Qué se intentó
- **Variación 1**: `GetApplicationExt()` -> Error 4002.
- **Variación 2**: `GetApplicationExt(None, None)` -> Error 7000.
- **Variación 3**: Flags `/min`, `/nologo`, `/headless` -> Error 7000.
- **Variación 4**: `GetApplication()` -> Devuelve `None` (no hay instancia activa).
- **Verificación**: El servidor de licencias en `PowerFactory.ini` es `10.2.36.213`.

## Por qué falló
- El error **4002** y **7000** son errores de bajo nivel de la API de PowerFactory. 
- El error 7000 a menudo se asocia con restricciones de sesión (Terminal Server / RDP) o falta de permisos para levantar el motor en modo headless sin una configuración de usuario válida.
- El problema es independiente del proyecto, ya que la falla ocurre durante la inicialización del objeto `Application`.

## Recomendación
- El entorno requiere revisión de la conectividad con el servidor de licencias `10.2.36.213`.
- Verificar si el usuario actual tiene permisos para ejecutar PowerFactory en modo motor (Engine).
- Probar la apertura manual de la GUI de PowerFactory para confirmar que la licencia es válida.
