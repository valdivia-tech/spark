# Spark ⚡

Agente de código eléctrico para DIgSILENT PowerFactory.

Spark recibe instrucciones en lenguaje natural, escribe scripts Python que usan la API de PowerFactory, los ejecuta, y devuelve resultados.

## Setup en la VM

```bash
# 1. Clonar
git clone <repo-url> spark
cd spark

# 2. Crear entorno virtual
python -m venv .venv
.venv\Scripts\activate  # Windows

# 3. Instalar dependencias
pip install -e .

# 4. Configurar
copy .env.example .env
# Editar .env con tu GOOGLE_API_KEY
```

## Uso

```bash
# Comando directo
python spark.py "corre un flujo de potencia en BD_2030.pfd"

# Modo interactivo
python spark.py --interactive

# Desde stdin
echo "lista todos los generadores activos" | python spark.py
```

## Estructura

```
spark/
├── spark.py          # CLI entry point
├── agent.py          # Loop ReAct (Gemini + bash/read/write)
├── config.py         # Configuración
├── prompts/
│   └── system.py     # System prompt con patrones de PowerFactory
├── workspace/        # Donde Spark escribe y ejecuta scripts
└── .env              # API keys (no se commitea)
```
