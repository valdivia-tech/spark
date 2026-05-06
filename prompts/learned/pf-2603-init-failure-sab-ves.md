# [FALLIDO] Flujo de Potencia 'Sabado Vespertino' en 2603 - Error de Inicialización API

Fecha: 2026-04-07
Tarea: "Abre el proyecto '2603-BD-OP-COORD-DMAP.pfd', activa 'Base SEN' y 'Sabado Vespertino', corre flujo con iopt_errlf=1 y reporta generación por tecnología."

## Qué se intentó
- **Inicialización API**: Se intentó instanciar PowerFactory usando `powerfactory.GetApplication()` y `powerfactory.GetApplicationExt()` con múltiples configuraciones.
- **Detección de Versión**: Se identificó que el entorno utiliza PowerFactory 2024 SP1 en `C:\Program Files\DIgSILENT\PowerFactory 2024 SP1\`.
- **Parámetros de Línea**: Se probó el uso de flags como `/min /nologo`, los cuales fueron rechazados por el ejecutable de esta versión específica.
- **Depuración de Entorno**: Se verificaron las rutas de sistema (`PATH`) y la carga correcta del módulo `powerfactory.pyd` (Python 3.12).

## Por qué falló
- **Error 4002 persistente**: El motor de PowerFactory devuelve el error 4002 de manera consistente. Este código indica que la aplicación no puede iniciarse, usualmente debido a:
    1. Problemas con el servicio de licencias en el servidor.
    2. Instancia de PowerFactory bloqueada o proceso huérfano (aunque `taskkill` no encontró procesos activos).
    3. Configuración de permisos o instalación de la API incompleta en esta VM específica.
- **Bloqueo de Proceso**: Una vez que un intento de inicialización falla con error 4002, los intentos subsiguientes en el mismo proceso de Python suelen fallar con error 7000, obligando a reiniciar el script.

## Recomendación
- El problema es de infraestructura del entorno de ejecución, no del script.
- Requiere intervención manual para verificar el estado de la licencia de PowerFactory en la máquina `VM-DIGSILENT-SM`.
- No intentar ejecuciones adicionales de la API en este entorno hasta que se valide la conectividad con el License Server.
