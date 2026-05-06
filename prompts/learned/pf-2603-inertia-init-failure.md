# [FALLIDO] Cálculo de Inercia por Zona en 2603 - Error de Inicialización API
Fecha: 2026-04-08
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd necesito INERCIA POR ZONA para cada uno de los 10 escenarios."

## Qué se intentó
- Se intentó inicializar la API de PowerFactory 2024 SP1 usando Python 3.12.
- Se configuraron los paths de sistema (`sys.path`) y variables de entorno (`PATH`) para apuntar a `C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\Python\3.12`.
- Se probaron métodos `GetApplication()` y `GetApplicationExt(None, None)`.
- Se intentó liberar procesos bloqueados con `taskkill /F /IM pf.exe`.

## Por qué falló
- El motor de PowerFactory devolvió consistentemente errores de inicialización:
  - **Error 7000**: "PowerFactory cannot be started again in the same process." (incluso después de limpiar procesos).
  - **Error 4002**: Error genérico de inicialización de la aplicación externa.
  - `GetApplication()` devolvió `None` sistemáticamente, impidiendo cualquier interacción con el proyecto o los escenarios.

## Recomendación
- El entorno de ejecución actual (VM) presenta una inestabilidad crítica con el motor de PowerFactory 2024 SP1 para este script. 
- Se recomienda verificar manualmente la disponibilidad de licencias en la estación de trabajo o intentar la ejecución con una versión de Python que coincida exactamente con la instalación de PowerFactory (ej. Python 3.12.x vs 3.12.y).
- Si el error persiste, el proyecto debe ser analizado mediante scripts DPL internos desde la interfaz de usuario de PowerFactory, ya que el acceso vía API externa está bloqueado.
