# Tidewave

Tidewave is the coding agent for full-stack web app development, deeply integrated with Python web frameworks, from the database to the UI. [See our website](https://tidewave.ai) for more information.

This project can also be used as a standalone Model Context Protocol (MCP) server for your editors.

We currently support Django but work for FastAPI and Flask is underway. Reach out if you want to help!

## Installation

### Django

Add `tidewave[django]` as a dependency to your `pyproject.toml`:

```
"tidewave[django] @ git+https://github.com/tidewave-ai/tidewave_python.git",
```

Then open up your `settings.py` and add the following after your `MIDDLEWARE` and `INSTALLED_APPS` definition:

```python
if DEBUG:
    INSTALLED_APPS.insert(0, "tidewave.django.apps.TidewaveConfig")
    MIDDLEWARE.insert(0, 'tidewave.django.Middleware')
```

And if you are using Jinja2, you need to add our extension too:

```python
JINJA2_ENVIRONMENT_OPTIONS = {
    "extensions": [
        "tidewave.jinja2.Extension"
    ],
}
```

#### Configuration

* `ALLOWED_HOSTS` - Tidewave use the same allowed origins as your app to validate access
* `TIDEWAVE["allow_remote_access"]` - Whether to allow remote connections (default `False`)
* `TIDEWAVE["team"]` - Enable your Tidewave Team configuration, such as `TIDEWAVE = {"team": {"id": "dashbit"}}`

## Troubleshooting

Tidewave expects your web application to be running on `localhost`. If you are not running on localhost, you may need to enable additional configuration, such as `allow_remote_access`.

If you want to use Docker for development, you either need to enable the configuration above or automatically redirect the relevant ports, as done by [devcontainers](https://code.visualstudio.com/docs/devcontainers/containers). See our [containers](https://hexdocs.pm/tidewave/containers.html) guide for more information.

### Content security policy

If you have enabled Content-Security-Policy, Tidewave will automatically enable "unsafe-eval" under `script-src` in order for contextual browser testing to work correctly. It also disables the `frame-ancestors` directive.

## Contributing

```bash
# Install
uv sync --only-dev

# Run tests
uv run python -m pytest

# Lint and format code
uv run ruff check --fix .
uv run ruff format .
```

## Acknowledgements

A thank you to [Rob Hudson](https://github.com/robhudson) for implementing the Django integration.

## License

Copyright (c) 2025 Dashbit

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at [http://www.apache.org/licenses/LICENSE-2.0](http://www.apache.org/licenses/LICENSE-2.0)

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
