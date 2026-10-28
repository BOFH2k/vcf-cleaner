import unittest

from helpers import load_cleaner


vcf_cleaner = load_cleaner()


class CombinedFixesTests(unittest.TestCase):
    def test_address_with_unrelated_phone_is_not_replaced(self):
        content = (
            "BEGIN:VCARD\nFN:Mainstr. 5 Sampletown 12345\nORG:Sample Company\n"
            "TEL:512345\nEND:VCARD"
        )
        self.assertEqual(vcf_cleaner.transform_vcard_content(content), content)

    def test_phone_replacement_and_deduplication_both_apply(self):
        content = (
            "BEGIN:VCARD\nFN:+4912345\nORG:MyCompany\nTEL:+4912345\n"
            "ADR:123 St\nADR:123 St\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertEqual(vcf_cleaner.extract_fn_value(transformed), "MyCompany")
        self.assertEqual(transformed.count("ADR:123 St"), 1)


if __name__ == "__main__":
    unittest.main()
