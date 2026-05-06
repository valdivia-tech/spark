# [FALLIDO] Flujo de potencia en 2603 con Restauración Manual y Despacho Balanceado
Fecha: 2026-04-06
Tarea: "Activar Laboral Diurno, restaurar red manual (outserv=0), cerrar interruptores, balancear despacho Pgen = 1.05 * Pload, fijar slack en máquina más grande y correr flujo."

## Qué se intentó
- Se activó el caso de estudio "Laboral Diurno".
- Se forzó `outserv=0` en todos los generadores, líneas y transformadores.
- Se cerraron todos los `ElmSwitch` (`nclose=1`).
- Se calculó el despacho total para ser 1.05 veces la carga (MW) y se escalaron los generadores proporcionalmente.
- Se fijó la máquina sincrónica de mayor potencia nominal (`sgn * ngn`) como Slack (`ip_ctrl=0` y bus `bus_type=1`).
- Se ejecutó el flujo de potencia con "Flat Start" (`iopt_fsta=1`).

## Por qué falló
- **Fragmentación Masiva**: A pesar de poner todo en servicio manualmente, se detectaron **20,377 barras aisladas**. Esto indica que la topología del proyecto 2603 depende críticamente de **Variaciones (`TypVara`)** y **Escenarios (`ElmScenario`)** que controlan el estado de servicio de subestaciones completas o cubículos. La restauración manual a nivel de elemento no es suficiente para unir la red.
- **Divergencia Inmediata**: Con ~80% de las barras aisladas, el flujo de potencia no puede converger ya que el Slack Bus probablemente no está conectado al grueso de la carga, o el sistema está roto en miles de islas.

## Recomendación
- El proyecto 2603 **requiere obligatoriamente la activación de un Escenario de Operación** (como 'Laboral Diurno') en lugar de restauración manual por script, ya que los escenarios manejan dependencias topológicas complejas que el script `outserv=0` ignora.
- No intentar correr flujo de potencia en este proyecto si el número de barras aisladas es superior a 100.
