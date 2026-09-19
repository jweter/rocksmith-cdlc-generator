import unittest
from json_utils import parse_json, validate_json

class TestJsonUtils(unittest.TestCase):
    def test_parse_json(self):
        # Test with a valid JSON file
        data = parse_json('test_data.json')
        self.assertIsNotNone(data)
        self.assertEqual(data['key'], 'value')

        # Test with a non-existent file
        data = parse_json('non_existent_file.json')
        self.assertIsNone(data)

        # Test with a file that is not valid JSON
        data = parse_json('invalid_json_file.json')
        self.assertIsNone(data)

    def test_validate_json(self):
        # Test with valid data and schema
        schema = {'key': str}
        data = {'key': 'value'}
        self.assertTrue(validate_json(data, schema))

        # Test with invalid data and schema
        schema = {'key': int}
        data = {'key': 'value'}
        self.assertFalse(validate_json(data, schema))

        # Test with missing key in data
        schema = {'key': str}
        data = {}
        self.assertFalse(validate_json(data, schema))

if __name__ == '__main__':
    unittest.main()
