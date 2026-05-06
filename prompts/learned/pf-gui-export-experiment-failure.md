# [FALLIDO] Exportar diagramas con GUI en PowerFactory 2024

Fecha: 2026-04-09
Tarea: "EXPERIMENTO: Necesito exportar diagramas graficos de PowerFactory con GUI. En vez de usar GetApplicationExt (engine mode), haz lo siguiente: 1) Usa subprocess.Popen para lanzar PowerFactory.exe con GUI... 3) Conecta con powerfactory.GetApplication() (sin Ext)..."

## Qué se intentó
- Se lanzó `PowerFactory.exe` mediante `subprocess.Popen`.
- Se esperaron tiempos de 15, 30, 45 y 60 segundos para asegurar la carga completa.
- Se intentó conectar usando `powerfactory.GetApplication()` (sin argumentos y con `None, None`).
- Se verificó la existencia del proceso con `tasklist`. El proceso se ejecutaba correctamente.
- Se intentó limpiar procesos previos (`taskkill`) para asegurar una instancia única.

## Por qué falló
- `powerfactory.GetApplication()` devolvió consistentemente `None`, indicando que no pudo encontrar o conectarse a la instancia de la GUI en la Tabla de Objetos en Ejecución (ROT).
- Al intentar `GetApplicationExt()` como último recurso, se obtuvo el error 7000 (común cuando hay problemas de licencia o múltiples instancias en conflicto).
- Es probable que el entorno de ejecución remoto restrinja la comunicación COM entre procesos o que la GUI se quede bloqueada en un diálogo inicial (ej. selección de usuario) que impide su registro COM.

## Recomendación
- El uso de la API en modo GUI (`GetApplication`) suele ser inestable en entornos de servidor o automatización remota. Se recomienda utilizar el modo motor (`GetApplicationExt`) para todas las tareas de automatización siempre que sea posible.
- Si es imprescindible exportar gráficos, considerar el uso de scripts DPL internos o verificar la configuración de auto-login y registro COM de PowerFactory en el servidor.
