# [FALLIDO] Detección de Flujos Reversos en 2603 (10 Escenarios)
Fecha: 2026-04-07
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd necesito detectar FLUJOS REVERSOS... activa Base SEN + escenario, slack distribuido con iopt_errlf=1... guarda flujos_por_escenario.json"

## Qué se intentó
1. **Inicialización y Carga**: Se intentó cargar el proyecto `2603-BD-OP-COORD-DMAP.pfd` y activar los 10 escenarios estándar (Laboral Diurno, etc.).
2. **Búsqueda de Casos**: `proj.GetContents("*.IntCase", 1)` devolvió una lista vacía o solo "Base SEN" después de la importación, impidiendo el procesamiento de los escenarios solicitados.
3. **Re-importación Limpia**: Se intentó borrar el proyecto y re-importarlo desde `../projects/2603/` para asegurar que todos los objetos estuvieran presentes.
4. **Depuración de Entorno**: Se intentó manejar errores de inicialización de la API (Código 7000) y verificar la visibilidad de los objetos mediante scripts de listado.

## Por qué falló
- **Inestabilidad de la API**: El entorno de ejecución presentó errores recurrentes de "PowerFactory cannot be started again in the same process" (Error 7000) y fallos de inicialización que devolvían `None` al intentar obtener la aplicación.
- **Visibilidad de Objetos**: A pesar de importar el proyecto correctamente, la búsqueda recursiva de `IntCase` no localizó los escenarios nombrados ("Laboral Diurno", etc.), posiblemente debido a una jerarquía de carpetas no estándar o a que los escenarios no se importaron correctamente en la sesión actual.
- **Límite de Intentos**: Se alcanzaron los límites de turnos sin lograr una ejecución estable que produjera el archivo de resultados solicitado.

## Recomendación
- Verificar manualmente en PowerFactory la ubicación exacta de los casos de estudio (Study Cases) dentro del proyecto `2603-BD-OP-COORD-DMAP`.
- Asegurarse de que el proceso de PowerFactory se cierre completamente entre ejecuciones de scripts si se presentan errores 7000.
- Considerar el uso de un script de inspección de carpetas más profundo para mapear la estructura de `IntFolder` antes de buscar casos por nombre.
