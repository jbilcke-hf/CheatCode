"""
Database operations for CheatCode.
"""

import yaml
from pathlib import Path
from typing import Dict, Any
from .config import get_database_path


def load_database() -> Dict[str, Any]:
    """Load existing database from YAML file."""
    db_path = get_database_path()
    if db_path.exists():
        with open(db_path, 'r') as f:
            return yaml.safe_load(f) or {"papers": []}
    return {"papers": []}


def save_database(database: Dict[str, Any]):
    """Save database to YAML file."""
    db_path = get_database_path()
    with open(db_path, 'w') as f:
        yaml.dump(database, f, default_flow_style=False, sort_keys=False)
