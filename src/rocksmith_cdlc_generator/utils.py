import json
from typing import Any, Optional

def parse_and_validate_json(json_data: str) -> Optional[dict]:
    try:
        data = json.loads(json_data)
        if not isinstance(data, dict):
            raise ValueError("JSON data must be a dictionary")
        return data
    except json.JSONDecodeError as e:
        print(f"Failed to decode JSON: {e}")
        return None
    except ValueError as e:
        print(f"Invalid JSON data: {e}")
        return None
