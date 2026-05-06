# [FALLIDO] Inicialización API PowerFactory 2024 SP1 en Proyecto 2603 - Sabado Diurno

Fecha: 2026-04-07
Tarea: "En el proyecto '2603-BD-OP-COORD-DMAP.pfd': 1. Mata procesos de PowerFactory... 2. Inicializa... 3. Activa Study Case 'Base SEN' y Escenario 'Sabado Diurno'... 4. Flujo de Potencia... 6. Mix por tecnología..."

## Qué se intentó
- **Inicialización Estándar**: Uso de `powerfactory.GetApplication()` y `powerfactory.GetApplicationExt()` con las rutas correctas para PowerFactory 2024 SP1 y Python 3.12.
- **Limpieza de Procesos**: Ejecución de `taskkill` para asegurar que no hubiera instancias previas bloqueando la API.
- **Verificación de Entorno**: Script de descubrimiento de rutas que confirmó que PowerFactory 2024 SP1 está instalado y tiene la API para Python 3.12.
- **Diferentes Métodos de GetApplication**: Intento de usar `GetApplicationExt(None, None)` y esperas (`time.sleep`) para estabilizar la carga.

## Por qué falló
- **Errores de Salida Críticos**: La API retornó consistentemente `powerfactory.ExitError: Exit with error code 4002` y `7000`. 
- **Inconsistencia del Proceso**: A pesar de que el proceso `PowerFactory.exe` no aparecía en la lista de tareas, la API reportaba "PowerFactory cannot be started again in the same process" o fallaba silenciosamente devolviendo `None`.
- **Restricción de Entorno**: Parece haber una incompatibilidad persistente en el entorno de ejecución actual con la versión 2024 SP1 de la API que impide la inicialización del objeto `app`.

## Recomendación
- **Validación Manual**: Verificar si la licencia de PowerFactory permite el acceso via API en este servidor.
- **Cambio de Versión**: Si el proyecto lo permite, intentar abrirlo con PowerFactory 2025 o 2026, donde la inicialización ha sido más estable en experiencias previas.
- **Reinicio de Nodo**: En algunos casos de error 4002/7000, un reinicio completo del sistema operativo o del contenedor es necesario para liberar recursos de la API.
