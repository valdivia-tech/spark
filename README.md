# Spark

Agente de codigo electrico para DIgSILENT PowerFactory.

Recibe instrucciones en lenguaje natural, escribe scripts Python que usan la API de PowerFactory, los ejecuta, y devuelve resultados.

## Setup

```bash
git clone <repo-url> spark
cd spark
cp .env.example .env       # editar con tu GOOGLE_API_KEY
uv sync
```

## Uso

```bash
# Comando directo
uv run spark "corre un flujo de potencia en BD_2030.pfd"

# Modo interactivo
uv run spark -i
```
