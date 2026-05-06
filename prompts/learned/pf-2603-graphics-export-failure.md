# [FALLIDO] Exportación de Diagramas Gráficos (ComWr / WriteWMF) en 2603

Fecha: 2026-04-08
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd, activa Base SEN + Laboral Diurno, corre el flujo... exporta los diagramas graficos a imagen usando el objeto ComWr de PowerFactory."

## Qué se intentó
- **Uso de ComWr**: Se configuró `iopt_rd` para PNG (4) y BMP (3), asignando `f_name`. El comando se ejecutaba (exit code 0) pero no generaba archivos porque no había un gráfico activo en el "Graphics Board".
- **Uso de app.WriteWMF()**: Se intentó activar gráficos con `grf.Show()` y `graphics_board.Show(grf)` antes de llamar a `WriteWMF`.
- **Activación de Páginas (SetVpage)**: Se buscó el objeto `SetDesktop` en el `StudyCase` para iterar sobre sus páginas y activarlas con `page.Show()`.
- **Creación Dinámica de Páginas**: Se intentó crear un `SetVpage` nuevo, asignarle el diagrama `IntGrfnet` a través del atributo `pGrfnet`, y luego mostrarlo.

## Por qué falló
- **Gráficos "Invisibles"**: En el entorno de ejecución de la API (especialmente si es `GetApplicationExt`), el `GraphicsBoard` a menudo no está inicializado o no tiene ventanas activas. Sin una ventana de gráfico "viva", tanto `ComWr` como `WriteWMF` fallan silenciosamente o no producen salida.
- **Error de Atributo en Show()**: El método `grf.Show()` (sobre un `IntGrfnet`) devolvió el error `'int' object is not a 'string' object`, sugiriendo una incompatibilidad en la firma del método o en la envoltura de Python para esa versión específica de PowerFactory.
- **Desktop Vacío**: En esta base de operación específica, el objeto `SetDesktop` del caso de estudio no contenía páginas pre-configuradas, lo que obligaba a crearlas dinámicamente, lo cual no fue suficiente para disparar el renderizado del gráfico.

## Recomendación
- **Verificar en GUI**: La exportación de gráficos vía API es altamente dependiente de que el proyecto tenga "Diagramas de Red" (no solo gráficos de resultados) abiertos y guardados en el caso de estudio.
- **Uso de DPL**: Si la API de Python falla, a veces un script DPL interno (`ComDpl`) que realice la exportación tiene mejor acceso al contexto de visualización.
- **Requisito de Motor**: Confirmar si el motor de PowerFactory utilizado permite renderizado de gráficos en modo "nologo/min" o si requiere una sesión con interfaz gráfica para inicializar los objetos de dibujo.
