# Contributing to PaR-EntBench

Thank you for your interest in contributing!

## Development setup

```bash
git clone https://github.com/vksingh/par-entbench.git
cd par-entbench
pip install -e ".[dev]"
docker compose up -d
```

## Code style

- Format with `ruff format src/`
- Lint with `ruff check src/`
- Type-check with `mypy src/`
- Test with `pytest`

## Adding new tasks

EntBench tasks live in `entbench/tasks/<class>/`. Each task is a JSON file following the schema in the dataset card (`docs/dataset_card.md`).

Before adding tasks:

1. Review the EntBench Convention Specification in `docs/convention_spec.md`
2. Validate against the bug-pattern budget (15% per pattern per class)
3. Include execution-based gold answers and per-task evaluator config

## Reporting issues

Use GitHub Issues. Include:

- Python version, OS
- Steps to reproduce
- Expected vs actual behavior
- Any relevant trace output

## Pull requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make changes with tests
4. Run `pytest` and ensure all checks pass
5. Submit PR with a clear description

## License

By contributing, you agree your contributions are licensed under Apache 2.0.
