from __future__ import annotations

import unittest

from app.server import _extract_form_values


class PayloadParserTest(unittest.TestCase):
    def test_extracts_from_form_data_dict(self) -> None:
        payload = {
            "flow": "payment",
            "formData": {"email": "ana@example.com", "amount": "10000"},
        }
        values = _extract_form_values(payload)
        self.assertEqual(values["email"], "ana@example.com")
        self.assertEqual(values["amount"], "10000")

    def test_extracts_from_fields_list(self) -> None:
        payload = {
            "fields": [
                {"name": "customer_name", "value": "Ana Silva"},
                {"name": "postal_code", "value": "01412-100"},
            ]
        }
        values = _extract_form_values(payload)
        self.assertEqual(values["customer_name"], "Ana Silva")
        self.assertEqual(values["postal_code"], "01412-100")

    def test_extracts_from_root_when_form_key_absent(self) -> None:
        payload = {
            "flow": "payment",
            "customer_name": "Ana Silva",
            "phone_number": "+55 11 98765-4321",
            "status": "ignored",
        }
        values = _extract_form_values(payload)
        self.assertEqual(values["customer_name"], "Ana Silva")
        self.assertEqual(values["phone_number"], "+55 11 98765-4321")
        self.assertNotIn("status", values)


if __name__ == "__main__":
    unittest.main()
