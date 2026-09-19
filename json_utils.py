import json
from typing import Any, Dict, Optional

def parse_json(file_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"Error decoding JSON from file: {file_path}")
        return None

def validate_json(data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False
    for key, value in schema.items():
        if key not in data:
            return False
        if not isinstance(data[key], value):
            return False
    return True
