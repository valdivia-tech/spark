# [FALLIDO] Flujo de potencia 2512-bus con recuperación de generación
Fecha: 2026-04-06
Tarea: "The previous attempt diverged due to a 2.1 GW generation deficit. In a SINGLE script, perform this recovery and simulation: 1. Setup... 2. Initialize... 3. Generation Recovery... 4. Balance Check... 5. Reference: Set the largest generator... as slack... 6. Solve... 7. Report..."

## Qué se intentó
- Se activó el proyecto `2512-bus.pfd`, escenario `ERV Maxima_Final_Dia_2030_ETF` y variaciones.
- Se ejecutaron los scripts DPL con "ON_OFF" en el nombre.
- Se activaron todos los generadores (`outserv=0`).
- Se inicializó la generación al 70% de la nominal para aquellos con `pgini=0`.
- Se escaló la generación para compensar un déficit de 2.1 GW hasta alcanzar `Pgen = Pload + 500 MW`.
- Se intentó establecer el generador más grande en la red de 220kV+ como slack (`ip_ctrl=0`).

## Por qué falló
- El flujo de potencia divergió (`error_code: 1`).
- El script de recuperación no logró identificar generadores en la red de 220kV+ para establecer el slack ("No generator found in 220kV+ network"). Esto probablemente se debió a que la navegación de atributos para encontrar la tensión de la barra conectada (`bus1.cterm.uknom`) no devolvió los valores esperados.
- Sin un slack bus activo y con potencia suficiente para absorber el desbalance final, el método de Newton-Raphson no converge.

## Recomendación
- Verificar los nombres de los atributos de conexión de los generadores en este modelo específico (ej. `bus1` vs `terminal`).
- Asegurar que al menos una red externa (`ElmXnet`) o un generador con despacho suficiente esté configurado como slack antes de correr el flujo.
- Considerar el uso de despacho distribuido (Slack Distribuido) si el desbalance es grande.
