import unittest

from helpers import load_cleaner


vcf_cleaner = load_cleaner()


class AddressDeduplicationTests(unittest.TestCase):
    def test_repeated_adr_lines_are_deduplicated(self):
        content = (
            "FN:John\nADR:123 Main St\nADR:123 Main St\n"
            "ADR:123 Main St\nADR:123 Main St"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertEqual(transformed.splitlines().count("ADR:123 Main St"), 1)


if __name__ == "__main__":
    unittest.main()
