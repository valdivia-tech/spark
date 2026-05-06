# [FALLIDO] Power Flow 'Sabado Diurno' 2603 - Error de Inicialización API (4002/7000)
Fecha: 2026-04-07
Tarea: "En el proyecto 2603-BD-OP-COORD-DMAP.pfd: 1. taskkill 2. GetApplicationExt() 3. Activa Base SEN y Sabado Diurno 4. ComLdf (iopt_pbal=4, iopt_init=1, iopt_errlf=1) 5. ElmDsl activo 6. Guardar resultados."

## Qué se intentó
- **Enfoque 1**: Inicialización estándar para PowerFactory 2026 Preview. Falló con Error 4002.
- **Enfoque 2**: Detección de versión (PowerFactory 2024 SP1 detectada) y ajuste de `sys.path` para Python 3.12. Falló con Error 4002.
- **Enfoque 3**: Script de diagnóstico comparando `GetApplication()` y `GetApplicationExt()`. El primero devuelve `None` y el segundo arroja Error 7000 (ya iniciado en el mismo proceso), confirmando que el motor queda en un estado bloqueado o inválido tras el primer fallo 4002.

## Por qué falló
- **Error Crítico de Inicialización (4002)**: El motor de PowerFactory no logra instanciarse en el entorno del runner. A pesar de que los archivos binarios existen y las rutas son correctas, la API de Python no logra establecer comunicación con el motor de ejecución.
- **Bloqueo de Proceso (7000)**: Una vez que un intento de inicialización falla, los intentos subsiguientes en el mismo script disparan el error 7000, impidiendo cualquier recuperación "en caliente".

## Recomendación
- Existe un problema recurrente de inicialización con la base 2603 en este entorno. Se recomienda verificar la disponibilidad del motor DIgSILENT en el servidor.
- No es un problema del script, sino de la capacidad del runner para levantar la instancia de PowerFactory 2024 SP1 necesaria para este proyecto.
