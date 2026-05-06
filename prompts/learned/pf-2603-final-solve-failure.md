# [FALLIDO] Flujo de potencia final en 2603-BD-OP-COORD-DMAP
Fecha: 2026-04-06
Tarea: "Activar escenario 'Laboral Diurno', ajustar despacho (Gen = Load * 1.05), configurar slack en el generador más grande y correr flujo de potencia AC."

## Qué se intentó
- Activación exitosa del escenario `Laboral Diurno` y del caso de estudio `Base SEN`.
- Cálculo del desbalance inicial: Generación (4724 MW) vs Carga (8892 MW).
- Aplicación de un factor de escalamiento de 1.9763 a todos los generadores activos (síncronos y estáticos) para alcanzar ~9337 MW.
- Configuración del generador síncrono más grande (`TER ANGAMOS U2`) como nodo de referencia (slack, `ip_ctrl=0`).
- Ejecución de flujo de potencia AC Newton-Raphson.

## Por qué falló
- El flujo de potencia divergió (`error_code: 1`) a pesar de tener un balance global razonable y un nodo de referencia definido.
- Diagnóstico: 0 barras aisladas (la topología es íntegra gracias al escenario), pero el sistema es extremadamente sensible o presenta problemas locales de reactiva/tensión que impiden la convergencia de Newton-Raphson.

## Recomendación
- El sistema de 2600+ barras requiere una sintonía fina de perfiles de tensión y límites de reactiva antes de intentar un flujo AC completo. 
- Se sugiere intentar un flujo DC inicial para verificar la factibilidad del despacho o usar una técnica de "escalamiento gradual" de la carga y generación desde un punto de operación conocido.
- El desbalance de 444 MW (5%) puede ser excesivo para ser absorbido por un solo nodo slack en un sistema tan grande sin causar colapso de tensión en áreas remotas.
