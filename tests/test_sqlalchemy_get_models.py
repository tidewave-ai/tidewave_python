"""
Tests for SQLAlchemy get_models tool
"""

import inspect
import pytest

from tidewave.sqlalchemy.models import get_models

from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import DeclarativeBase


class TestSQLAlchemyGetModels:
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

        assert "Base" not in result
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

        # Should include the specific test file name and line number
        expected_line = inspect.getsourcelines(LocationTest)[1]
        assert "LocationTest at tests/test_sqlalchemy_get_models.py:" in result
        assert str(expected_line) in result
