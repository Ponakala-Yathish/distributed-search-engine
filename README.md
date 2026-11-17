# Distributed Search Engine

A four-VM distributed search engine built with ZeroTier, Hadoop 3.3.6, Spark/PySpark 3.3.4, Apache Iceberg 1.8.1, Parquet, FastAPI, Next.js, BM25, and distributed PageRank.

## Status

| Area | Status |
|---|---|
| Central configuration and environment overrides | Implemented and unit-tested |
| Environment and connectivity audits | Implemented |
| Ingestion, validation, deduplication, Iceberg MERGE | Implemented; requires actual VM integration verification |
| Distributed inverted index and PageRank | Implemented; requires actual two-worker execution verification |
| Versioned Parquet export and atomic serving switch | Implemented; requires actual VM integration verification |
| FastAPI search service | Implemented and integration-tested locally |
| Next.js frontend | Implemented; local build verified separately |
| Distributed fault injection | Documented; destructive experiments are opt-in and not run in this repository |

## VM Roles

| Node | Role | Services |
|---|---|---|
| VM1 | Ingestion | Spark client only |
| VM2 | Storage | HDFS NameNode/DataNode, Spark worker |
| VM3 | Compute | Spark master/worker, HDFS DataNode |
| VM4 | Search | FastAPI and frontend; no Spark/HDFS daemons |

The ZeroTier addresses and roles are defined once in `config/cluster.yaml`. `DSE_VM1_HOST` through `DSE_VM4_HOST` can override them without source changes.

## Repository Layout

```text
config/                  Central cluster and runtime configuration
ingestion/               JSONL parsing, validation, deduplication, Iceberg MERGE
indexing/                Distributed tokenizer, postings, statistics, export
pagerank/                Distributed graph construction and iterative PageRank
search_service/          In-memory FastAPI index serving and ranking
frontend/                Next.js, TypeScript, and Tailwind interface
scripts/                 Audit, setup, run, export, deploy, and verification tools
tests/                   Unit, integration, and distributed-contract tests
benchmarks/              Reproducible latency and relevance evaluation
docs/                    Architecture, operations, algorithms, and viva notes
```

## Quick Start by VM

```bash
git clone <repository-url> distributed-search-engine
cd distributed-search-engine
cp config/.env.example config/.env
```

Install the VM-specific Python environment first using `docs/setup.md`, then run:

```bash
bash scripts/audit_environment.sh
bash scripts/validate_config.sh
```

Follow `docs/setup.md` for the exact ordered setup. The official workflow is:

```bash
bash scripts/run_phase0.sh
bash scripts/export_index.sh --phase 0
bash scripts/deploy_search.sh --version 0
bash scripts/run_phase1.sh
bash scripts/export_index.sh --phase 1
bash scripts/deploy_search.sh --version 1
```

The phase commands run on their assigned VMs. See `docs/deployment.md` for the command-to-VM mapping.

## Tests

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements/dev.txt
pytest tests/
ruff check .
mypy config ingestion indexing pagerank search_service
```

`tests/integration` that require Spark are skipped when PySpark or the Iceberg runtime is unavailable. Local tests are not evidence of four-VM verification.

## Official Data

Place the official files under `data/datasets/`:

```text
data/datasets/pages.jsonl
data/datasets/changes.jsonl
```

The official Drive currently provides Phase 1 as `changes.json`; `scripts/run_phase1.sh` accepts either extension. Dataset files and local `.env` files are excluded from Git.

## Documentation

- `docs/architecture.md`
- `docs/setup.md`
- `docs/deployment.md`
- `docs/algorithms.md`
- `docs/compatibility.md`
- `docs/fault_tolerance.md`
- `docs/benchmarks.md`
- `docs/troubleshooting.md`
- `docs/verification_checklist.md`
- `docs/viva_questions.md`
