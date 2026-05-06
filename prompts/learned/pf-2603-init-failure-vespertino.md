# [FALLIDO] Inicialización API PowerFactory 2024 SP1 en Proyecto 2603 - Sabado Vespertino
Fecha: 2026-04-07
Tarea: "Abrir el proyecto '2603-BD-OP-COORD-DMAP.pfd', activar 'Base SEN' y 'Sabado Vespertino', y correr flujo de potencia con iopt_pbal=4 e iopt_init=0."

## Qué se intentó
- **Enfoque 1**: Uso de la ruta de PowerFactory 2024 SP1 con Python 3.12 (versión instalada en el sistema).
- **Enfoque 2**: Alternancia entre `GetApplication()` y `GetApplicationExt()` para intentar instanciar el objeto aplicación.
- **Enfoque 3**: Scripts de diagnóstico para verificar la carga del módulo `powerfactory.pyd`. El módulo carga correctamente, pero el motor no arranca.

## Por qué falló
- **Error 4002**: El método `GetApplicationExt()` devuelve consistentemente el código de error 4002. Este error indica que el motor de PowerFactory no puede iniciarse.
- **Error 7000**: Al intentar re-inicializar en el mismo proceso, se genera el error 7000, indicando un bloqueo de proceso o que el motor ya está marcado como fallido/activo.
- **Detección de Aplicación Nula**: Aunque `GetApplication()` no lanza una excepción, devuelve `None`, lo que imposibilita cualquier operación sobre el proyecto.

## Recomendación
- El entorno parece tener un conflicto de licencia o de configuración con la versión 2024 SP1 instalada.
- Se requiere una revisión manual de la instalación de PowerFactory en el servidor o verificar si el servicio de licencias está disponible para la ejecución vía API.
- Evitar re-intentos de inicialización en el mismo script si el primer intento falla con 4002.
