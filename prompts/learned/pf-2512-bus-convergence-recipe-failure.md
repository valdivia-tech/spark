# [FALLIDO] Flujo de potencia 2512-bus con secuencia de activación específica
Fecha: 2026-04-06
Tarea: "Activar caso 'Base SEN 2030 Día', escenario 'ERV Maxima_Final_Dia_2030_ETF', variaciones 'Flujo 2030', 'Flujo_2030', 'Plan de Obras', ejecutar DPLs 'ON_OFF', y correr flujo AC"

## Qué se intentó
- Se activó el caso de estudio y el escenario de operación especificados.
- Se activaron las variaciones solicitadas.
- Se ejecutaron todos los scripts DPL que contenían 'ON_OFF' en el nombre para inicializar plantas.
- Se verificó la existencia de un nodo Slack. Al no haber uno por defecto, se configuró el generador más grande en Alto Jahuel / Quillota 220kV como Slack.
- Se ejecutó un flujo de potencia AC balanceado.

## Por qué falló
- El flujo de potencia divergió (`error_code = 1`).
- El diagnóstico reveló un desbalance masivo de potencia activa: Generación total ~7,445 MW vs Carga total ~9,561 MW (déficit de ~2,116 MW).
- Un desbalance de esta magnitud es difícil de manejar para un solo nodo Slack, lo que probablemente causó la divergencia antes de alcanzar convergencia matemática.

## Recomendación
- Revisar si los scripts 'ON_OFF' están conectando toda la generación necesaria para el escenario 2030.
- Considerar el uso de escalamiento de generación o el activación de más plantas antes de correr el flujo.
- El modelo sigue presentando problemas de balance carga-generación estructurales para este escenario.
