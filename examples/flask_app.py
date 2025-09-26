"""
uv run python examples/flask_app.py
"""
# ruff: noqa: T201 -- allow print statements

from flask import Flask, render_template

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

from tidewave.flask import Tidewave


class Base(DeclarativeBase):
    pass


def create_app():
    """Create a Flask app with MCP middleware"""
    app = Flask(__name__)

    # Configure SQLite in-memory database
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Initialize SQLAlchemy
    db = SQLAlchemy(model_class=Base)
    db.init_app(app)

    # Define a sample model
    class User(db.Model):
        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(80), nullable=False)
        email = db.Column(db.String(120), unique=True, nullable=False)

        def __repr__(self):
            return f"<User {self.name}>"

    # Create tables
    with app.app_context():
        db.create_all()

    @app.route("/")
    def home():
        return render_template(
            "home.html",
            title="Flask + Tidewave MCP + SQLAlchemy",
            message="Welcome to Flask with Jinja2 template debugging and SQLAlchemy integration!",
        )

    return app


def main():
    """Run the Flask app with MCP middleware"""
    app = create_app()
    app.debug = True

    tidewave = Tidewave()
    tidewave.init_app(app)

    print("Starting Flask server on http://localhost:8000")
    print("Try sending MCP requests to http://localhost:8000/tidewave/mcp")
    print("SQLAlchemy tools (get_models, execute_sql_query) are auto-detected and available")
    print("Press Ctrl+C to stop")

    from wsgiref.simple_server import make_server

    server = make_server("localhost", 8000, app)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")


if __name__ == "__main__":
    main()
