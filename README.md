# Stock Movement Analyzer

`stock-movement-analyzer` is a local-first research engine that turns recent market moves into concise, investor-style briefings. It combines Yahoo Finance market data, Tavily-powered web intelligence retrieval, source credibility scoring, and LangGraph-driven adaptive research loops with fully local LLM inference through Ollama.

It keeps searching until the evidence is strong enough, then delivers a clean markdown report for one or more tickers with a confidence score for each explanation.

## Agent Architecture

![Agent Architecture Diagram](assets/Agent_Architecture.png)

The analyzer uses a compact LangGraph pipeline:

1. `fetch_prices` gathers recent price action and sector context for each ticker.
2. `generate_stock_query` asks the model for an authoritative search query.
3. `search_and_filter_news` pulls web results, scores source credibility, and keeps the strongest evidence.
4. `analyze_movement` explains the move, while `reflect_and_deepen` decides whether another research pass is needed.
5. `save_ticker_report` stores the per-ticker briefing and `compile_final_report` assembles the portfolio summary.

The diagram uses the shorter `search_news` label for the implemented `search_and_filter_news` step.

## What it does

For each ticker, the analyzer:

1. Pulls recent price data and measures the move.
2. Generates a targeted search query for authoritative sources.
3. Searches the web and scores sources by credibility.
4. Writes or extends an explanation of the move.
5. Reflects on the explanation, assigns confidence, and decides whether another search pass is needed.
6. Produces a polished final report.

## Features

- Multi-ticker portfolio analysis in one run
- Adaptive confidence-gated research loops that keep searching until the evidence is strong enough
- Per-ticker source isolation so evidence from one symbol never bleeds into another report
- Source scoring across primary, trusted, acceptable, and junk domains
- Private, local-first analysis with fully local LLM inference through Ollama or LMStudio
- CLI entry point for normal Python usage
- LangGraph export for Studio or API-based workflows

## Project Structure

```text
.
|-- assets/
|   `-- Agent_Architecture.png      # LangGraph workflow diagram used in this README
|-- src/
|   |-- __init__.py                 # package exports and lazy graph access
|   |-- __main__.py                 # `python -m stock_movement_analyzer`
|   |-- cli.py                      # CLI argument parsing and command entrypoint
|   |-- config.py                   # settings and dependency builders
|   |-- credibility.py              # source scoring and filtering
|   |-- graph.py                    # LangGraph assembly and exported graph
|   |-- market_data.py              # Yahoo Finance data collection
|   |-- nodes.py                    # graph node implementations
|   |-- prompts.py                  # LLM prompt templates
|   |-- routing.py                  # graph routing decisions
|   |-- search.py                   # Tavily search formatting helpers
|   |-- state.py                    # shared graph state definitions
|   `-- py.typed                    # type hint marker for downstream consumers
|-- tests/
|   |-- test_credibility.py         # credibility scoring tests
|   |-- test_graph.py               # graph smoke and regression tests
|   |-- test_reporting.py           # report formatting tests
|   `-- test_routing.py             # graph routing tests
|-- .dockerignore                   # trims the Docker build context
|-- .env.example                    # sample environment variables
|-- .gitignore                      # local-only files excluded from git
|-- Dockerfile                      # container image definition
|-- langgraph.json                  # LangGraph Studio/API entrypoint
|-- LICENSE                         # MIT license
|-- pyproject.toml                  # package metadata and dependencies
|-- README.md                       # project documentation
`-- uv.lock                         # locked dependency resolution for uv
```

The source stays flat under `src/`; setuptools maps that directory to the installed `stock_movement_analyzer` package name.

## Requirements

- Python 3.10+
- A Tavily API key
- A local model served through Ollama or LMStudio

## Working Directory

Unless noted otherwise, run the project commands below from the project root, meaning the folder that contains `README.md`, `src/`, `.env.example`, and `Dockerfile`.

Example on macOS/Linux:

```bash
cd /path/to/stock_movement_analyzer
```

Example on Windows PowerShell:

```powershell
cd C:\path\to\stock_movement_analyzer
```

## Installation

Run these from the project root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

For local development tools such as Ruff, install the optional dev extra:

```bash
pip install -e ".[dev]"
```

On Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

Optional dev tools:

```powershell
pip install -e '.[dev]'
```

## Configuration

From the project root, copy the example environment file:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Important variables:

- `TAVILY_API_KEY`: required for web search
- `LLM_PROVIDER`: `ollama` or `lmstudio`
- `LOCAL_LLM`: model name to use
- `OLLAMA_BASE_URL`: Ollama server URL
- `LMSTUDIO_BASE_URL`: LMStudio OpenAI-compatible URL
- `MAX_RESEARCH_LOOPS`: max research passes per ticker
- `CONFIDENCE_THRESHOLD`: stop early when the explanation is strong enough

To make the analyzer search more aggressively, increase `MAX_RESEARCH_LOOPS` and raise `CONFIDENCE_THRESHOLD` so it continues iterating until it has stronger supporting evidence.

### Ollama example

This command can be run from any directory because it talks to your local Ollama server:

```bash
ollama pull gemma4:e4b-it-q8_0
```

```dotenv
LLM_PROVIDER=ollama
LOCAL_LLM=gemma4:e4b-it-q8_0
OLLAMA_BASE_URL=http://localhost:11434
TAVILY_API_KEY=tvly-xxxxx
```

### LMStudio example

```dotenv
LLM_PROVIDER=lmstudio
LOCAL_LLM=gemma4:e4b-it-q8_0
LMSTUDIO_BASE_URL=http://localhost:1234/v1
TAVILY_API_KEY=tvly-xxxxx
```

## CLI Usage

Run these from the project root after activating your virtual environment:

```bash
stock-movement-analyzer NVDA AAPL TSLA
```

Specify a different lookback window and write the report to disk:

```bash
stock-movement-analyzer NVDA AAPL TSLA \
  --lookback-days 5 \
  --max-research-loops 3 \
  --confidence-threshold 80 \
  --output report.md
```

`report.md` is just an example output path. Treat it as generated local output rather
than a tracked project artifact.

You can also run it as a module from the project root after activating your virtual environment:

```bash
python -m stock_movement_analyzer NVDA AAPL TSLA
```

## LangGraph Usage

This project also exports a compiled graph through `langgraph.json`.

Install the LangGraph CLI separately, then run this from the project root after `pip install -e .`:

```bash
langgraph dev
```

The graph export is:

```text
stock_movement_analyzer.graph:graph
```

LangGraph imports the installed package entrypoint, so run `pip install -e .` before starting `langgraph dev`.

## Example Output

The final markdown report is designed to read like a short investor briefing:

```md
### NVDA
*Moved UP 4.12% over 5 days ($104.23 -> $108.52)*

NVIDIA's move was primarily driven by...

**Confidence:** 87% (HIGH CONFIDENCE)

**Sources (credibility-scored):**
* [PRIMARY 95/100] ...
```

## Testing

Run the unit test suite from the project root after activating your virtual environment:

```bash
python -m unittest discover -s tests -v
```

The suite includes a multi-ticker regression that ensures one symbol's sources do not
leak into another symbol's report.

Run Ruff if you installed the optional dev tools:

```bash
ruff check .
```

## Publishing Hygiene

Before sharing the repository publicly, do a quick clean-room verification pass:

```bash
pip install -e ".[dev]"
python -m unittest discover -s tests -v
ruff check .
```

Keep real secrets in your local `.env` only. Generated outputs such as `report.md`
should stay local as well; `.gitignore` already excludes both.

## Docker

Start Docker Desktop or otherwise make sure the Docker daemon is running before building.

Build the image from the project root:

```bash
docker build -t stock-movement-analyzer .
```

The container uses `stock-movement-analyzer` as its entrypoint, so running the image with no extra arguments shows the CLI help:

```bash
docker run --rm stock-movement-analyzer
```

Run an analysis and write the output back to your working directory:

```bash
docker run --rm \
  --env-file .env \
  -v "$(pwd):/workspace" \
  stock-movement-analyzer NVDA AAPL TSLA \
  --output /workspace/report.md
```

On Windows PowerShell:

```powershell
docker run --rm `
  --env-file .env `
  -v "${PWD}:/workspace" `
  stock-movement-analyzer NVDA AAPL TSLA `
  --output /workspace/report.md
```

If Ollama or LMStudio is running on your host machine, do not leave the base URL set to `localhost` for container runs. Use `host.docker.internal` instead, for example:

```dotenv
OLLAMA_BASE_URL=http://host.docker.internal:11434
LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1
```

The image keeps `.env.example` as a template only. Pass real environment variables at runtime with `--env-file` or individual `-e` flags when launching the container.