# [FALLIDO] Exploración de Objetos Gráficos en Proyecto 2603
Fecha: 2026-04-08
Tarea: "Activar Base SEN + Laboral Diurno en 2603-BD-OP-COORD-DMAP.pfd y explorar/exportar objetos gráficos (IntGrfnet, SetVipage, etc.)"

## Qué se intentó
- **Inicialización de la API**: Se intentó usar la ruta de PowerFactory 2024 SP1. Se descubrió que llamar a `GetApplication()` antes de `GetApplicationExt()` bloqueaba el proceso (Error 4002/7000). Solo funcionó llamar directamente a `GetApplicationExt()`.
- **Búsqueda de Objetos**: Se realizó una búsqueda recursiva (`GetContents("*.ClassName", 1)`) de las clases `IntGrfnet`, `SetVipage`, `IntGrf`, y `SetDeskpage`.
- **Exportación de Imágenes**: Se intentó usar los métodos `WritePNG()` y `WriteWMF()` sobre los objetos encontrados para guardarlos en el directorio de resultados.

## Por qué falló
- **Ausencia de Salida Gráfica**: Aunque el script terminó sin errores de ejecución (exit_code 0), no se generaron archivos de imagen en el directorio de resultados.
- **Incapacidad de Exportación Headless**: Es probable que los métodos `WritePNG`/`WriteWMF` requieran que el diagrama esté "abierto" o que la aplicación no esté en modo motor puro para renderizar gráficos.
- **Estructura del Proyecto**: Los diagramas en bases operativas del CEN suelen estar organizados en jerarquías complejas o depender de objetos `ComVis` que no fueron instanciados correctamente.

## Recomendación
- Validar la existencia de diagramas mediante una inspección manual previa o un script que liste específicamente la jerarquía de carpetas "Graphics".
- Probar el uso del objeto de comando `ComVis` para la exportación de diagramas, asegurándose de configurar los parámetros de escala y resolución.
- Confirmar si la licencia de PowerFactory disponible permite la exportación de gráficos en modo API/Engine.
