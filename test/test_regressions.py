import importlib.util
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

    def test_n_that_is_only_a_duplicated_email_is_removed(self):
        content = (
            "BEGIN:VCARD\nFN:Guest\nN:;;;(sample.family@example.com)\n"
            "ORG:Real Name\nEMAIL:sample.family@example.com\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertNotIn("N:;", transformed)
        self.assertIn("EMAIL:sample.family@example.com", transformed)

    def test_n_keeps_its_name_when_only_the_email_part_duplicates(self):
        content = (
            "BEGIN:VCARD\nFN:Guest\nN:Sample;Family;;;(sample.family@example.com)\n"
            "ORG:Real Name\nEMAIL:sample.family@example.com\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertIn("N:Sample;Family;;;", transformed)
        self.assertIn("EMAIL:sample.family@example.com", transformed)

    def test_n_email_without_a_matching_email_line_is_kept(self):
        content = (
            "BEGIN:VCARD\nFN:Guest\nN:Sample;Family;;;(sample.family@elsewhere.com)\n"
            "ORG:Real Name\nEMAIL:sample.family@example.com\nEND:VCARD"
        )
        self.assertEqual(vcf_cleaner.transform_vcard_content(content), content)

    def test_n_split_into_subfields_of_a_name_is_removed(self):
        content = (
            "BEGIN:VCARD\nFN:Kfz-Werkstatt\nORG:Sample Org\n"
            "EMAIL;TYPE=WORK:info@sample-org.de\n"
            "N:de;info@sample-org;;;\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertNotIn("N:de;", transformed)
        self.assertIn("EMAIL;TYPE=WORK:info@sample-org.de", transformed)

    def test_n_name_is_kept_even_when_an_email_repeats_it(self):
        content = (
            "BEGIN:VCARD\nFN:Sample\nORG:Sample Org\n"
            "EMAIL:sample.family@example.com\n"
            "N:Sample;Family;;;\nEND:VCARD"
        )
        self.assertEqual(vcf_cleaner.transform_vcard_content(content), content)

    def test_n_split_email_matching_ignores_non_ascii_letters(self):
        content = (
            "BEGIN:VCARD\nFN:Sample\nORG:Sample Org\n"
            "EMAIL:nöme@example.de\n"
            "N:de;nöme@example;;;\nEND:VCARD"
        )
        transformed = vcf_cleaner.transform_vcard_content(content)
        self.assertNotIn("N:de;", transformed)
        self.assertIn("EMAIL:nöme@example.de", transformed)

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


class ValidationTests(unittest.TestCase):
    """The --validate switch: structural rules and optional library tiers."""

    def test_validation_accepts_a_well_formed_card(self):
        content = (
            "BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Sample Org\r\nORG:Sample Org\r\n"
            "N:Org;;Sample;;\r\nTEL:+49123456789\r\n"
            "END:VCARD"
        )
        self.assertEqual(vcf_cleaner.validate_vcard(content), [])

    def test_validation_flags_a_missing_group_end(self):
        content = (
            "BEGIN:VCARD\r\nFN:Sample Org\r\n"
            "ORG:Sample Org\r\nTEL:+49123456789\r\n"
        )
        problems = vcf_cleaner.validate_vcard(content)
        self.assertIn("a BEGIN: marker is never matched by its END: marker", problems)

    def test_validation_flags_a_line_that_is_not_a_property(self):
        content = (
            "BEGIN:VCARD\r\nFN:Sample Org\r\nstray line\r\nEND:VCARD\r\n"
        )
        problems = vcf_cleaner.validate_vcard(content)
        self.assertTrue(any("not a property line" in p for p in problems))

    def test_validation_flags_an_overlong_physical_line(self):
        content = (
            "BEGIN:VCARD\r\nFN:" + "x" * (vcf_cleaner.MAX_LINE_BYTES + 1)
            + "\r\nEND:VCARD\r\n"
        )
        problems = vcf_cleaner.validate_vcard(content)
        self.assertTrue(any("bytes" in p for p in problems))

    def test_validation_flags_orphan_continuation_and_duplicate_fn(self):
        orphan = " more text\r\nBEGIN:VCARD\r\nFN:Sample Org\r\nEND:VCARD\r\n"
        self.assertTrue(
            any("continues a line" in p
                for p in vcf_cleaner.validate_vcard(orphan)))
        duplicated = (
            "BEGIN:VCARD\r\nFN:Sample Org\r\nFN:Other Name\r\nEND:VCARD\r\n"
        )
        self.assertTrue(
            any("FN appears" in p
                for p in vcf_cleaner.validate_vcard(duplicated)))

    def test_validation_degrades_without_the_optional_libraries(self):
        """A plain interpreter still gets the structural rules."""
        if importlib.util.find_spec("vobject") is not None:
            raise unittest.SkipTest("vobject is installed in this interpreter")
        content = (
            "BEGIN:VCARD\r\nFN:Sample Org\r\nORG:Sample Org\r\nTEL:+49123456789\r\n"
        )
        self.assertEqual(
            vcf_cleaner.validate_vcard(content),
            ["a BEGIN: marker is never matched by its END: marker"])

    @unittest.skipIf(importlib.util.find_spec("vobject") is None,
                     "vobject is installed from a uv-managed venv, see README")
    def test_vobject_tier_adds_checks_of_its_own(self):
        """An unterminated parameter quote is invisible to the structural rules."""
        content = (
            'BEGIN:VCARD\r\nFN;A="B:Sample Org\r\nEND:VCARD\r\n'
        )
        problems = vcf_cleaner.validate_vcard(content)
        self.assertTrue(any(p.startswith("vobject rejects it") for p in problems))

    @unittest.skipIf(importlib.util.find_spec("icalendar") is None,
                     "icalendar is installed from a uv-managed venv, see README")
    def test_ical_tier_is_opt_in_and_stricter_than_vcard_3_0(self):
        """A short N subfield list is legal in VCard 3.0 but not for icalendar."""
        content = (
            "BEGIN:VCARD\r\nFN:Sample Org\r\nN:Sample;;\r\nEND:VCARD\r\n"
        )
        without = vcf_cleaner.validate_vcard(content)
        with_ical = vcf_cleaner.validate_vcard(content, validate_ical=True)
        self.assertEqual(without, [])
        self.assertTrue(
            any(p.startswith("icalendar rejects it") for p in with_ical))

    @unittest.skipIf(importlib.util.find_spec("vobject") is None,
                     "vobject is installed from a uv-managed venv, see README")
    def test_invalid_output_exits_with_a_status_of_its_own(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input"
            output = root / "output"
            source.mkdir()
            content = (
                "BEGIN:VCARD\nFN:+49123456789\nORG:Sample Org\n"
                "TEL:+49123456789\nstray line\n"
            )
            (source / "broken.vcf").write_text(content, encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(source), str(output),
                 "--validate"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("[INVALID OUTPUT] broken.vcf", result.stdout)
        self.assertIn("Files with invalid output:", result.stdout)

    @unittest.skipIf(importlib.util.find_spec("vobject") is not None,
                     "only about the missing-library bootstrap path")
    def test_requesting_validation_without_a_parser_explains_the_setup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "input"
            output = root / "output"
            source.mkdir()
            (source / "plain.vcf").write_text(
                "BEGIN:VCARD\nFN:Sample Org\nEND:VCARD\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(source), str(output),
                 "--validate"],
                capture_output=True,
                text=True,
                check=False,
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("uv pip install", result.stdout)
        self.assertIn("Missing: vobject", result.stdout)


if __name__ == "__main__":
    unittest.main()
