"""
Shared pytest configuration and fixtures for CodeGraph.
"""

import os
import sys
from pathlib import Path

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from codegraph.db import db
from seed import seed_all


@pytest.fixture(scope="session", autouse=True)
def initialize_graph():
    """Seed the knowledge graph once before running the test suite."""
    seed_all()


@pytest.fixture
def fresh_graph():
    """Provides a guaranteed clean, freshly seeded graph for mutating tests."""
    seed_all()
    return db
