# [FALLIDO] Inicialización API y Flujo 'Domingo Madrugada' en 2603
Fecha: 2026-04-07
Tarea: "Inicializar PF, activar 'Base SEN' y 'Domingo Madrugada', correr flujo con slack distribuido y reporte por tecnología. Si falla, deshabilitar ElmDsl."

## Qué se intentó
- **Inicialización Simple**: Se intentó `powerfactory.GetApplication()` sin parámetros para usar la versión predeterminada.
- **Inicialización Extendida**: Se intentó `powerfactory.GetApplicationExt()` con las rutas de Python 3.12 para PowerFactory 2024 SP1 (confirmadas mediante `dir`).
- **Limpieza de Procesos**: Se verificó que no hubiera instancias colgadas de PowerFactory mediante `tasklist`.
- **Estrategia de Reintento**: Se estructuró el script para deshabilitar modelos `ElmDsl` y usar `iopt_errlf=1` para forzar la ejecución en caso de errores de DLL.

## Por qué falló
- **Error 4002 persistente**: El motor de PowerFactory devolvió consistentemente el error 4002 ("Exit with error code 4002") o la función de inicialización devolvió `None`.
- **Restricción de Proceso**: Se observó el mensaje "PowerFactory cannot be started again in the same process" en intentos consecutivos, lo que sugiere que el entorno de ejecución retiene estados de la librería que impiden una re-inicialización limpia una vez que el primer intento falla.
- **Falla de Acceso**: A pesar de que las rutas a los binarios son correctas, la aplicación no logra instanciarse, posiblemente por problemas de licencia o configuración del entorno PowerFactory 2024 SP1 en esta sesión particular.

## Recomendación
- El error 4002 es un error de bajo nivel de DIgSILENT. No es un error de sintaxis de Python. 
- En sesiones futuras, si el error 4002 persiste tras el primer intento, es probable que la base de datos o el motor de PowerFactory requieran un reinicio manual del servicio o del entorno de trabajo, ya que la API de Python no puede recuperarse de este estado por sí sola.
- No intentar múltiples métodos de inicialización (`GetApplication` seguido de `GetApplicationExt`) en el mismo script si el primero falla catastróficamente, ya que la DLL de DIgSILENT a menudo bloquea el proceso.
