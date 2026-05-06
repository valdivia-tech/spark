# [FALLIDO] Flujo de Potencia 2603 Sabado Vespertino - Falla de Inicialización de Aplicación

Fecha: 2026-04-07
Tarea: "En el proyecto '2603-BD-OP-COORD-DMAP.pfd', activa el Study Case 'Base SEN' y el Escenario 'Sabado Vespertino'. Corre flujo de potencia con iopt_pbal=4 y reporta generación por tecnología."

## Qué se intentó
- Se intentó inicializar la API de PowerFactory usando `GetApplicationExt()` y `GetApplication()`.
- Se intentó importar el proyecto desde la ruta `../projects/2603/2603-BD-OP-COORD-DMAP.pfd`.
- Se implementó la lógica de clasificación por prefijos (HE, TER, PFV, PE, BESS).

## Por qué falló
- **Error 4002**: Al intentar obtener la instancia de la aplicación con `GetApplicationExt()`, el sistema devolvió `powerfactory.ExitError: Exit with error code 4002`. Este error suele indicar que no hay licencias disponibles, que la instancia ya está en uso o un problema de entorno con el engine de PowerFactory.
- **Falla de Importación**: En intentos posteriores, el script reportó que la importación falló, posiblemente debido a que la instancia previa no se cerró correctamente o el entorno quedó en un estado inconsistente.
- **Persistencia de Archivos**: Los archivos de resultados (`resumen_flujo.json`) no se encontraron en el directorio esperado tras la ejecución, confirmando que el proceso no completó la fase de cálculo.

## Recomendación
- Verificar la disponibilidad de licencias de PowerFactory en el entorno de ejecución.
- Asegurarse de que no existan procesos `PowerFactory.exe` huérfanos antes de iniciar una nueva tarea.
- Revisar si el proyecto ya está importado en la base de datos del usuario para evitar conflictos de importación.
- Validar la ruta exacta del archivo .pfd en el contenedor de proyectos.
