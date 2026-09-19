import unittest
from src.rocksmith_cdlc_generator.utils import parse_and_validate_json

class TestUtils(unittest.TestCase):
    def test_parse_and_validate_json_valid(self):
        json_data = '{"key": "value"}'
        result = parse_and_validate_json(json_data)
        self.assertIsNotNone(result)
        self.assertEqual(result, {"key": "value"})

    def test_parse_and_validate_json_invalid(self):
        json_data = '{"key": "value"'
        result = parse_and_validate_json(json_data)
        self.assertIsNone(result)

    def test_parse_and_validate_json_not_dict(self):
        json_data = '["key", "value"]'
        result = parse_and_validate_json(json_data)
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
