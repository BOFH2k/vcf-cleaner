import unittest

from helpers import load_cleaner


vcf_cleaner = load_cleaner()


class DryRunFixTests(unittest.TestCase):
    def test_content_with_trailing_newline_is_unchanged(self):
        content = "FN:John\nORG:Company\n"
        self.assertEqual(vcf_cleaner.transform_vcard_content(content), content)

    def test_content_without_trailing_newline_is_unchanged(self):
        content = "FN:John\nORG:Company"
        self.assertEqual(vcf_cleaner.transform_vcard_content(content), content)


if __name__ == "__main__":
    unittest.main()
