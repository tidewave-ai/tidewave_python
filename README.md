# Tidewave

> Tidewave Web for Django and Flask is currently in alpha testing!

Tidewave is the coding agent for full-stack web app development, deeply integrated with Python web frameworks, from the database to the UI. [See our website](https://tidewave.ai) for more information.

This project can also be used as a standalone Model Context Protocol (MCP) server for your editors.

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

If you are using Jinja2, you need to add our extension too (preferably in `DEBUG` mode only):

```python
JINJA2_ENVIRONMENT_OPTIONS = {
    "extensions": [
        "tidewave.jinja2.Extension"
    ],
}
```

Note Tidewave only runs in DEBUG mode.

#### Settings

* `ALLOWED_HOSTS` - Tidewave use the same allowed origins as your app to validate access
* `TIDEWAVE["allow_remote_access"]` - Whether to allow remote connections (default `False`)
* `TIDEWAVE["team"]` - Enable your Tidewave Team configuration, such as `TIDEWAVE = {"team": {"id": "dashbit"}}`

### Flask

Add `tidewave[flask]` as a dependency to your `pyproject.toml`:

```
"tidewave[flask] @ git+https://github.com/tidewave-ai/tidewave_python.git",
```

Now, in your application definition, you can initialize the `Tidewave` class and pass your Flask application to `init_app`:

```python
if app.debug:
    from tidewave.flask import Tidewave
    tidewave = Tidewave()
    tidewave.init_app(app)
```

Tidewave will automatically detect if your Flask application is using SQLAlchemy and Jinja2 and configure them automatically.

Note Tidewave only runs when `app.debug` is `True`. Therefore, remember to start your dev server with the `--debug` flag. If you are setting `app.debug` programatically, remember to do so before you call `tidewave.init_app`.

#### Configuration

When initializing `Tidewave()`, the following options are supported:

- `allow_remote_access:` allow remote connections when True (default False)
- `allowed_origins:` list of allowed origin hosts (default [])
- `team`: enable Tidewave Web for teams

### FastAPI

> Tidewave Web is currently not supported for FastAPI.

Add `tidewave[fastapi]` as a dependency to your `pyproject.toml`:

```
"tidewave[fastapi] @ git+https://github.com/tidewave-ai/tidewave_python.git",
```

Now, in your application definition, you can initialize the `Tidewave` class and pass your FastAPI application to `install`. Note that you only want to do this in **development mode**:

```python
# Your preferable way of detecting dev mode.
is_dev = os.environ.get("RUN_MODE", None) == "development"

if is_dev:
    from tidewave.fastapi import Tidewave
    tidewave = Tidewave()
    tidewave.install(app)
```

If you are using Jinja2, you need to add our extension too:

```python
if is_dev:
    # ...

    from tidewave.jinja2 import Extension
    templates.env.add_extension(Extension)
```

If you are using SQLAlchemy, then you need to pass your `Base` class and the underlying engine as arguments to install:

```python
tidewave.install(app, sqlalchemy_base=Base, sqlalchemy_engine=engine)
```

*Note: when using [SQLModel](https://sqlmodel.tiangolo.com/), you should set `sqlalchemy_base=SQLModel`.*

#### Configuration

When initializing `Tidewave()`, the following options are supported:

- `allow_remote_access:` allow remote connections when True (default False)
- `allowed_origins:` list of allowed origin hosts (default [])
- `team`: enable Tidewave Web for teams

## Troubleshooting

Tidewave expects your web application to be running on `localhost`. If you are not running on localhost, you may need to enable additional configuration, such as `allow_remote_access`.

Furthermore, Tidewave only runs while in `DEBUG`/`app.debug` mode on all frameworks.

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
