import unittest
from app.mapper import map_case_event

class TestMapper(unittest.TestCase):
    def test_mapping(self):
        event = {
            "payload": {
                "case_id": "C1",
                "title": "T1",
                "extra": "ignore"
            }
        }
        res = map_case_event(event)
        self.assertEqual(res['case_id'], "C1")
        self.assertEqual(res['title'], "T1")
        self.assertNotIn("extra", res)

if __name__ == "__main__":
    unittest.main()
