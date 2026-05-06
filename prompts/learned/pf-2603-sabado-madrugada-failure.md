# [FALLIDO] Flujo de Potencia 'Sabado Madrugada' en 2603 - Errores de Inicialización y Atributos

Fecha: 2026-04-07
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: 1. Activar 'Base SEN' y 'Sabado Madrugada'. 2. Configurar ComLdf (pbal=4, init=1, errlf=1). 3. Ejecutar flujo. 4. Clasificar generación por prefijos. 5. Reportar totales y pérdidas."

## Qué se intentó
- **Inicialización API**: Se intentó usar `GetApplicationExt()` y `GetApplication()`. Se encontró que `GetApplicationExt()` devolvía errores **4002** y **7000** de manera recurrente en el entorno de ejecución.
- **Ruta del Proyecto**: Se identificó que el archivo `.pfd` se encontraba en una subcarpeta `../projects/2603/` y no en la raíz de `projects`.
- **Cálculo de Pérdidas**: Se intentó acceder al atributo `m:Psum` directamente desde el objeto de comando `ComLdf`, lo cual provocó un `AttributeError` ya que ese objeto no contiene los resultados del sistema (estos están en los elementos o en un objeto de sumario).

## Por qué falló
- **Conflictos de Sesión**: El motor de PowerFactory no pudo inicializarse correctamente en múltiples intentos debido a errores de bajo nivel (4002/7000), lo que sugiere una instancia bloqueada o falta de permisos en el modo "engine".
- **Error de Codificación**: El uso de `app.GetFromStudyCase("ComLdf").GetAttribute("m:Psum")` es incorrecto. Las pérdidas deben calcularse sumando las potencias en ambos extremos de líneas y transformadores (`m:P:bus1 + m:P:bus2`).

## Recomendación
- **Limpieza de Procesos**: Asegurarse de que no existan procesos `powerfactory.exe` huérfanos antes de iniciar el script.
- **Acceso a Resultados**: Siempre verificar la existencia de atributos con `HasAttribute` antes de `GetAttribute`. Para totales del sistema en bases grandes, iterar sobre elementos es más fiable que depender de objetos de sumario globales que pueden no estar inicializados.
- **Estructura de Carpetas**: Usar `dir /s` para localizar el archivo `.pfd` si no se encuentra en la ruta esperada.
