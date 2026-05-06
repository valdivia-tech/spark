# [FALLIDO] Flujo de potencia en sistema 2512-bus (Chile SEN) - Intento 2
Fecha: 2026-03-27
Tarea: "run a power flow on projects/2512-bus.pfd"

## Qué se intentó
- **Importación y búsqueda de casos:** Se importó el proyecto y se iteró por todos los Study Cases disponibles (`Base SEN 2030 D\u00eda`, `Base SEN 2030 Noche`, `Base SEN 2035 D\u00eda`, etc.).
- **Activación de Escenarios:** Se detectaron y activaron escenarios como `ERV Maxima_Final_Dia_2030_ETF` esperando que estos configuraran el despacho.
- **Análisis de Balance:** Se encontró un desbalance persistente de ~2.1 GW entre la carga (9.5 GW) y la generación (7.4 GW) en el caso "D\u00eda".
- **Búsqueda de Slack:** 
  - Se buscaron `ElmXnet` (0 encontrados).
  - Se buscaron `ElmSym` con `i_c_pctrl = 2` (ninguno configurado como slack).
  - Se intentó forzar generadores grandes (`HE RALCO`, `HE COLBUN`) como slack mediante script.
- **Ajustes de Convergencia:** Se probó con Slack Distribuido (`iopt_slk=1` en `ComLdf`).

## Por qué falló
- **Divergencia Inmediata:** Ninguna de las configuraciones probadas logró que el Newton-Raphson convergiera (`error_code = 1`).
- **Desbalance de Potencia:** Sin un nodo Slack que absorba el déficit de 2 GW, el sistema es matemáticamente inconsistente para un flujo de potencia.
- **Falta de Referencia:** El modelo parece depender de un estado inicial o script de despacho externo no incluido o no trivial de activar vía API sin documentación previa del proyecto.

## Recomendación
- El proyecto requiere una revisión manual en la interfaz de PowerFactory para identificar qué elemento debe actuar como Slack.
- No intentar correr flujo en este archivo sin antes equilibrar Pgen y Pload manualmente o mediante un escenario válido que sí contenga una referencia de fase (Slack).
