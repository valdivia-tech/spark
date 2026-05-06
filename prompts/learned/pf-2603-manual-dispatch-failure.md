# [FALLIDO] Flujo de Potencia con Redespacho Manual en 2603 (Laboral Diurno)
Fecha: 2026-05-18
Tarea: "En proyecto 'projects/2603/2603-BD-OP-COORD-DMAP.pfd': 1. Activate 'Laboral Diurno'. 2. Activate all generators. 3. Perform a basic generation dispatch (load+3%). 4. Set Slack. 5. Run power flow (Automatic + Flat start). 6. Report results."

## Qué se intentó
- Se activó el proyecto y se buscó el escenario 'Laboral Diurno'.
- Se activaron TODOS los generadores (`outserv=0`).
- Se realizó un despacho proporcional distribuido (Load: 8892 MW, Gen: 9159 MW).
- Se seleccionó 'TER TOCOPILLA U16-TG-TV' como Slack.
- Se ejecutó el flujo de potencia en modo Automático y luego con Flat Start.

## Por qué falló
- El flujo de potencia divergió en ambos intentos (error_code = 1).
- La activación masiva de generadores y el redespacho manual probablemente rompieron el balance operativo pre-configurado en la base de datos de operación de CEN.
- La presencia de islas aisladas o la falta de estabilidad de tensión debido a perfiles planos (usetp=1.0) en un sistema tan grande suelen causar divergencia.

## Recomendación
- Evitar el redespacho manual en bases operacionales de CEN a menos que sea estrictamente necesario.
- No activar todos los generadores; confiar en el estado guardado en el escenario SCADA.
- Usar slack distribuido (`iopt_dis=1` en `ComLdf`) en lugar de una sola máquina para sistemas grandes desbalanceados.
