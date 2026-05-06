# Inventory of Project Objects
Fecha: 2026-04-06
Tarea: "In project 'projects/2512-bus.pfd', perform a complete inventory of Study Cases, Scenarios, Variations, and DPL scripts. Analyze for '2030' dispatch management."

## Lecciones aprendidas
- `IntScenario` objects do NOT have an `IsActive()` method; their active status must be checked via `app.GetActiveProject().GetActiveScenario()` or `study_case.GetActiveScenario()`.
- `IntScheme` (Variations) typically have an `IsActive()` method.
- Project objects like `IntScenario` and `IntScheme` are best found using `GetContents("*.ClassName", 1)` for recursive search within the project.
- Content of `IntScenario` can be summarized by counting `IntMditem` (modification items).

## Script
```python
import sys, os, time, json
import powerfactory

# Initialization and project loading with cache (standard boilerplate)
# ...

def get_inventory():
    start_time = time.time()
    # ... import and activate proj ...

    # 1. Study Cases
    study_cases = proj.GetContents("*.IntCase", 1)
    active_case = app.GetActiveStudyCase()
    cases_list = [{"name": c.loc_name, "active": c == active_case} for c in study_cases]

    # 2. Scenarios
    scenarios = proj.GetContents("*.IntScenario", 1)
    active_scenario = None
    if active_case:
        try: active_scenario = active_case.GetActiveScenario()
        except: pass
    if not active_scenario:
        try: active_scenario = proj.GetActiveScenario()
        except: pass

    scenarios_list = [
        {
            "name": sc.loc_name, 
            "modifications_count": len(sc.GetContents("*.IntMditem", 1)),
            "is_active": sc == active_scenario
        } for sc in scenarios
    ]

    # 3. Variations
    variations = proj.GetContents("*.IntScheme", 1)
    variations_list = [
        {
            "name": var.loc_name,
            "active": var.IsActive() == 1 if hasattr(var, "IsActive") else False
        } for var in variations
    ]

    # 4. DPL Scripts
    dpls_list = [d.loc_name for d in proj.GetContents("*.ComDpl", 1)]

    # Analysis
    # ... search for 2030 clues in names ...
    
    # Save to results/inventory.json
```
