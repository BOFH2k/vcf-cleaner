import unittest

from helpers import load_cleaner


vcf_cleaner = load_cleaner()


class FinalFixesTests(unittest.TestCase):
    def test_zero_prefixed_phone_is_detected(self):
        content = (
            "BEGIN:VCARD\nFN:05551234567\nORG:MyCompany\n"
            "TEL:05551234567\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertEqual(vcf_cleaner.extract_fn_value(transformed), "MyCompany")

    def test_duplicate_lines_are_removed_without_changing_fn(self):
        content = "BEGIN:VCARD\nFN:John Doe\nADR:123 St\nADR:123 St\nEND:VCARD"
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertEqual(vcf_cleaner.extract_fn_value(transformed), "John Doe")
        self.assertEqual(transformed.count("ADR:123 St"), 1)

    def test_trailing_newline_is_preserved(self):
        content = "BEGIN:VCARD\nFN:John\nEND:VCARD\n"
        self.assertEqual(vcf_cleaner.transform_vcard_content(content), content)


if __name__ == "__main__":
    unittest.main()
