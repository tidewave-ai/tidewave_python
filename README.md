# Tidewave

See `examples/` folder.

## Development

### Requirements

- Python 3.8+
- [uv](https://docs.astral.sh/uv/) (recommended)

### Install with uv

```bash
# Install
uv sync --only-dev

# Run tests
uv run python -m pytest

# Lint and format code
uv run ruff check --fix .
uv run ruff format .
```
