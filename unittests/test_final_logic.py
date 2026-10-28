import unittest

from helpers import load_cleaner


vcf_cleaner = load_cleaner()


class FinalLogicTests(unittest.TestCase):
    def test_fn_address_matches_any_line(self):
        content = (
            "BEGIN:VCARD\nFN:Mainstr. 16\nORG:Sample Org\n"
            "X-ADDR:Mainstr. 16\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertEqual(vcf_cleaner.extract_fn_value(transformed), "Sample Org")

    def test_n_is_removed_when_it_matches_adr(self):
        content = (
            "BEGIN:VCARD\nFN:John Doe\nN:Mainstr. 16\nORG:Sample Org\n"
            "ADR:Mainstr. 16\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertEqual(vcf_cleaner.extract_fn_value(transformed), "John Doe")
        self.assertNotIn("N:Mainstr. 16", transformed)

    def test_fn_and_n_changes_can_both_apply(self):
        content = (
            "BEGIN:VCARD\nFN:Mainstr. 16\nN:Mainstr. 16\nORG:Sample Org\n"
            "ADR:Mainstr. 16\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertEqual(vcf_cleaner.extract_fn_value(transformed), "Sample Org")
        self.assertNotIn("N:Mainstr. 16", transformed)


if __name__ == "__main__":
    unittest.main()
