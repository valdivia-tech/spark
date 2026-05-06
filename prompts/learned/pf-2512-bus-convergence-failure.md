# [FALLIDO] Correr flujo de potencia en proyecto 2512-bus (SEN Chile)
Fecha: 2026-03-27
Tarea: "run a power flow on projects/2512-bus.pfd"

## Qué se intentó
- **Importación y Activación:** El proyecto ya existía como `2512-BD-LP-COORD-DPL_V1`. Es un modelo masivo de ~80,000 objetos y ~31,000 barras (aparentemente el Sistema Eléctrico Nacional de Chile).
- **Ejecución de ComLdf:** Se intentó correr el flujo de potencia en el Study Case por defecto ("Base SEN 2030 Día") y en "Base SEN 2030 Noche".
- **Diagnóstico de Convergencia:** El flujo no convergió (`error_code = 1`). 
- **Análisis de Balance:** Se detectó un desbalance masivo en el primer caso: ~1.2 GW de generación programada en `ElmSym` frente a ~9.5 GW de carga en `ElmLod`. Incluso sumando `ElmGenstat` (~6.1 GW), seguía habiendo un déficit.
- **Búsqueda de Slack:** Se buscaron Redes Externas (`ElmXnet`) y generadores en modo slack (`i_c_pctrl = 2`), pero la búsqueda no arrojó resultados válidos o los atributos no coincidían con lo esperado para este modelo específico.

## Por qué falló
- **Falta de Referencia (Slack):** El sistema no parece tener un nodo slack activo en los casos de estudio proporcionados, o el desbalance entre generación y carga es tan grande que el algoritmo Newton-Raphson diverge inmediatamente.
- **Complejidad del Modelo:** Con 31,000 barras, cualquier error de configuración en transformadores o límites de reactiva impide la convergencia sin una depuración manual exhaustiva.
- **Límite de Turnos:** Se agotaron los intentos tratando de encontrar un Study Case que estuviera balanceado o de identificar el atributo correcto para forzar un slack.

## Recomendación
- Este proyecto parece requerir una inicialización específica (posiblemente a través de un script de "Escenario" o "Despacho" interno del proyecto) antes de correr el flujo. 
- Verificar manualmente en PowerFactory qué generador o red externa debe actuar como Slack.
- Si se intenta de nuevo, empezar por listar todos los `ElmXnet` y verificar su estado (`outserv`) y modo de control.
