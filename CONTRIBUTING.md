# Contributing

Thanks for your interest in improving `MOS Evaluation Toolkit`.

## Development Principles

- Keep the project self-contained and easy to run locally.
- Avoid introducing unnecessary infrastructure (database, queue, external auth).
- Preserve anonymity guarantees in the UI and API.
- Prefer simple JSON- and file-based workflows.

## Local Development

```bash
cd mos_eval
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py --reload
```

## Before Sending Changes

Please verify the following when relevant:

1. The app still launches with `python run.py`
2. Panel scanning works for the default folder layout
3. Audio URLs remain anonymized
4. Aggregation still produces JSON / Markdown / CSV outputs

Useful checks:

```bash
python scripts/_self_check.py
python scripts/_anon_check.py
python scripts/aggregate.py --include-drafts
```

## Data and Generated Files

Do not commit:

- real evaluation audio
- user session JSONs under `data/results/`
- generated reports under `data/reports/`
- local virtual environments

The repository keeps only sample directory structures and metadata templates.

## Code Style

- Keep frontend code dependency-free unless there is a strong reason not to
- Prefer clear naming over clever abstractions
- Keep the UI bilingual when editing user-facing copy
- Preserve backward compatibility of existing directory conventions when possible

