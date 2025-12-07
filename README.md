# Tidewave

Tidewave is the coding agent for full-stack web app development. Integrate Claude Code, OpenAI Codex, and other agents with your web app and web framework at every layer, from UI to database. [See our website](https://tidewave.ai) for more information.

This project supports Django, FastAPI, and Flask. It can also be used as a standalone Model Context Protocol (MCP) server for your editors.

## Installation

### Django

Add `tidewave[django]` as a dependency to your `pyproject.toml`:

```
"tidewave[django]",
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

Now make sure [Tidewave is installed](https://hexdocs.pm/tidewave/installation.html) and you are ready to connect Tidewave to your app.

#### Settings

* `TIDEWAVE["allow_remote_access"]` - Whether to allow remote connections (default `False`)
* `TIDEWAVE["team"]` - Enable your Tidewave Team configuration, such as `TIDEWAVE = {"team": {"id": "dashbit"}}`

Note Tidewave only runs in DEBUG mode.

### Flask

Add `tidewave[flask]` as a dependency to your `pyproject.toml`:

```
"tidewave[flask]",
```

Now, in your application definition, you can initialize the `Tidewave` class and pass your Flask application to `init_app`:

```python
if app.debug:
    from tidewave.flask import Tidewave
    tidewave = Tidewave()
    tidewave.init_app(app)
```

Note Tidewave only runs when `app.debug` is `True`. Therefore, remember to start your dev server with the `--debug` flag. If you are setting `app.debug` programatically, remember to do so before you call `tidewave.init_app`.

Now make sure [Tidewave is installed](https://hexdocs.pm/tidewave/installation.html) and you are ready to connect Tidewave to your app.

#### Configuration

When initializing `Tidewave()`, the following options are supported:

- `allow_remote_access:` allow remote connections when True (default False)
- `team`: enable Tidewave Web for teams

Tidewave will automatically detect if your Flask application is using SQLAlchemy and Jinja2 and configure them automatically.

### FastAPI

> Tidewave Web is currently not supported for FastAPI.

Add `tidewave[fastapi]` as a dependency to your `pyproject.toml`:

```
"tidewave[fastapi]",
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

Now make sure [Tidewave is installed](https://hexdocs.pm/tidewave/installation.html) and you are ready to connect Tidewave to your app.

#### Configuration

When initializing `Tidewave()`, the following options are supported:

- `allow_remote_access:` allow remote connections when True (default False)
- `team`: enable Tidewave Web for teams

## Troubleshooting

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
