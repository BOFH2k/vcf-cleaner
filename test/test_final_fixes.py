import importlib.util
import sys
import os

# Load vcf-cleaner.py
spec = importlib.util.spec_from_file_location("vcf_cleaner", "vcf-cleaner.py")
vcf_cleaner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vcf_cleaner)

def test_phone_detection():
    print("Testing Phone Detection (0-prefixed)...")
    # FN is phone, TEL has same phone, ORG is different.
    # Content should change FN to ORG.
    content = "BEGIN:VCARD\nFN:05551234567\nORG:MyCompany\nTEL:05551234567\nEND:VCARD"
    transformed = vcf_cleaner.transform_vcard_content(content)
    old_fn = vcf_cleaner.extract_fn_value(content)
    new_fn = vcf_cleaner.extract_fn_value(transformed)
    if old_fn == "05551234567" and new_fn == "MyCompany":
        print("  SUCCESS: 0-prefixed phone detected and replaced.")
    else:
        print(f"  FAILED: Expected FN 'MyCompany', got '{new_fn}' (Old FN: '{old_fn}')")

def test_dry_run_reporting_dedup():
    print("\nTesting Dry-Run Reporting (Deduplication)...")
    # Content has duplicate ADR, no FN change.
    content = "BEGIN:VCARD\nFN:John Doe\nADR:123 St\nADR:123 St\nEND:VCARD"
    transformed = vcf_cleaner.transform_vcard_content(content)
    
    if transformed != content:
        old_fn = vcf_cleaner.extract_fn_value(content)
        new_fn = vcf_cleaner.extract_fn_value(transformed)
        if old_fn == new_fn:
            # This simulates the logic in batch_process_vcards
            print("  SUCCESS: Deduplication detected, FN is same.")
            print("           In dry-run, this will now show '(Deduplication applied)')")
        else:
            print(f"  FAILED: FN changed unexpectedly. Old: {old_fn}, New: {new_fn}")
    else:
        print("  FAILED: Content should have changed due to deduplication")

def test_trailing_newline_preservation():
    print("\nTesting Trailing Newline Preservation...")
    content = "BEGIN:VCARD\nFN:John\nEND:VCARD\n"
    transformed = vcf_cleaner.transform_vcard_content(content)
    if transformed == content:
        print("  SUCCESS: Trailing newline preserved, no change reported.")
    else:
        print(f"  FAILED: Content changed unexpectedly. \nOriginal: {repr(content)}\nTransformed: {repr(transformed)}")

if __name__ == "__main__":
    test_phone_detection()
    test_dry_run_reporting_dedup()
    test_trailing_newline_preservation()
