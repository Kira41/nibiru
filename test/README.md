# Test workspace

This folder is the dedicated local test workspace for the Nibiru repository.

## Why this exists
- Keeps fake data and smoke tests isolated from production scripts.
- Gives us a repeatable place to validate future updates before shipping them.
- Avoids hitting live services by using local fixtures, temporary SQLite databases, and lightweight HTTP serving.

## Contents
- `run_all.py`: main entry point that runs the full local test suite.
- `test_tracker_workflow.py`: validates tracker parsing and stay-analysis using fake JSONL data.
- `test_accounting_parser.py`: validates PMTA/accounting parsing helpers with fake CSV rows.
- `test_dns_shaker.py`: validates DNS inspection logic with controlled fake DNS responses.
- `fixtures/`: reusable fake data files.

## Standard command
```bash
python test/run_all.py
```

## Notes for future updates
- When adding or changing code, prefer adding a matching `test_*.py` file here.
- Keep tests deterministic.
- Prefer fake/local data over external network calls.
- If a feature depends on HTTP logs, CSV input, or HTML output, add a fixture file here first.
