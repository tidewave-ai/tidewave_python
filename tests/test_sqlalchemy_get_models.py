"""
Tests for SQLAlchemy get_models tool
"""

import pytest

from tidewave.sqlalchemy.models import get_models

# Test with real SQLAlchemy if available, otherwise skip
try:
    from sqlalchemy import Column, Integer, String
    from sqlalchemy.orm import DeclarativeBase

    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False


@pytest.mark.skipif(not SQLALCHEMY_AVAILABLE, reason="SQLAlchemy not available")
class TestSQLAlchemyGetModels:
    """Test suite for SQLAlchemy models discovery using real SQLAlchemy"""

    def test_get_models_returns_function(self):
        """Test that get_models returns a callable function."""

        class Base(DeclarativeBase):
            pass

        discover_function = get_models(Base)
        assert callable(discover_function)

    def test_get_models_discovers_concrete_models(self):
        """Test discovery of concrete SQLAlchemy models."""

        class Base(DeclarativeBase):
            pass

        class User(Base):
            __tablename__ = "users"
            id = Column(Integer, primary_key=True)
            name = Column(String(50))

        class Product(Base):
            __tablename__ = "products"
            id = Column(Integer, primary_key=True)
            name = Column(String(100))

        discover_function = get_models(Base)
        result = discover_function()

        assert "User" in result
        assert "Product" in result
        assert result.count("* ") == 2

    def test_get_models_excludes_abstract_models(self):
        """Test that abstract models are excluded."""

        class Base(DeclarativeBase):
            pass

        class AbstractModel(Base):
            __abstract__ = True
            id = Column(Integer, primary_key=True)

        class ConcreteModel(Base):
            __tablename__ = "concrete"
            id = Column(Integer, primary_key=True)

        discover_function = get_models(Base)
        result = discover_function()

        assert "ConcreteModel" in result
        assert "AbstractModel" not in result

    def test_get_models_excludes_base_class(self):
        """Test that the base class itself is excluded."""

        class Base(DeclarativeBase):
            pass

        class Child(Base):
            __tablename__ = "children"
            id = Column(Integer, primary_key=True)

        discover_function = get_models(Base)
        result = discover_function()

        assert "Child" in result
        assert "Base" not in result

    def test_get_models_no_models_found(self):
        """Test behavior when no concrete models are found."""

        class EmptyBase(DeclarativeBase):
            pass

        discover_function = get_models(EmptyBase)
        result = discover_function()

        assert "No concrete models found that inherit from EmptyBase" in result

    def test_get_models_sorts_alphabetically(self):
        """Test that models are sorted alphabetically by name."""

        class Base(DeclarativeBase):
            pass

        class ZebraModel(Base):
            __tablename__ = "zebras"
            id = Column(Integer, primary_key=True)

        class AlphaModel(Base):
            __tablename__ = "alphas"
            id = Column(Integer, primary_key=True)

        discover_function = get_models(Base)
        result = discover_function()

        lines = result.strip().split("\n")
        assert "AlphaModel" in lines[0]
        assert "ZebraModel" in lines[1]

    def test_source_location_included(self):
        """Test that source locations are included in output."""

        class Base(DeclarativeBase):
            pass

        class LocationTest(Base):
            __tablename__ = "location_test"
            id = Column(Integer, primary_key=True)

        discover_function = get_models(Base)
        result = discover_function()

        # Should include source location with line number
        assert "LocationTest at " in result
        assert ".py:" in result
