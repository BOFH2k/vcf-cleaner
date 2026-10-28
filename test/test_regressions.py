import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import load_cleaner


vcf_cleaner = load_cleaner()
SCRIPT = Path(__file__).resolve().parents[1] / "vcf-cleaner.py"


class ImprovementRegressionTests(unittest.TestCase):
    def test_address_matching_preserves_token_identity(self):
        content = (
            "BEGIN:VCARD\nFN:ABC 123\nORG:Real Name\n"
            "X-NOTE:321 CBA\nEND:VCARD"
        )
        self.assertEqual(vcf_cleaner.transform_vcard_content(content), content)

    def test_address_matching_can_ignore_token_order_and_punctuation(self):
        content = (
            "BEGIN:VCARD\nFN:Mainstr. 16\nORG:Sample Org\n"
            "X-ADDR:16 Mainstr\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertEqual(vcf_cleaner.extract_fn_value(transformed), "Sample Org")

    def test_case_insensitive_grouped_fn_preserves_its_parameters(self):
        content = (
            "BEGIN:VCARD\nitem1.fn;LANGUAGE=en:1234567\n"
            "org:Example Corp\ntel:1234567\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertIn("item1.fn;LANGUAGE=en:Example Corp", transformed)
        self.assertEqual(vcf_cleaner.extract_fn_value(transformed), "Example Corp")

    def test_n_that_duplicates_tel_is_removed(self):
        content = (
            "BEGIN:VCARD\nFN:Guest\nN:;+49123456789;;;\n"
            "ORG:Real Name\nTEL:+49 123 456-789\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertNotIn("+49123456789", transformed)
        self.assertIn("TEL:+49 123 456-789", transformed)

    def test_n_phone_without_tel_match_is_kept(self):
        content = (
            "BEGIN:VCARD\nFN:Guest\nN:;+49123456789;;;\n"
            "ORG:Real Name\nTEL:+49999999999\nEND:VCARD"
        )
        self.assertEqual(vcf_cleaner.transform_vcard_content(content), content)

    def test_n_with_a_name_is_kept_even_if_it_holds_a_tel_number(self):
        content = (
            "BEGIN:VCARD\nFN:Guest\nN:Mustermann;+49123456789;;;\n"
            "ORG:Real Name\nTEL:+49123456789\nEND:VCARD"
        )
        self.assertEqual(vcf_cleaner.transform_vcard_content(content), content)

    def test_file_processing_error_sets_nonzero_command_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input"
            output = root / "output"
            source.mkdir()
            (source / "unreadable.vcf").mkdir()

            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(source), str(output)],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Error with file unreadable.vcf", result.stdout)
        self.assertIn("Files that failed:", result.stdout)


if __name__ == "__main__":
    unittest.main()
