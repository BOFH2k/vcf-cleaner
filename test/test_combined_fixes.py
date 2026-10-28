import importlib.util
import os

# Load vcf-cleaner.py
spec = importlib.util.spec_from_file_location("vcf_cleaner", "vcf-cleaner.py")
vcf_cleaner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vcf_cleaner)

def test_address_as_fn():
    print("Testing Address in FN (should NOT be replaced)...")
    # FN is an address with numbers, which could be mistaken for a phone number by regex
    # if letters are not checked.
    content = "BEGIN:VCARD\nFN:Mainstr. 5 Sampletown 12345\nORG:Sample Company\nTEL:512345\nEND:VCARD"
    transformed = vcf_cleaner.transform_vcard_content(content)
    
    if content == transformed:
        print("  SUCCESS: Address was correctly identified as not a phone number.")
    else:
        print(f"  FAILED: Address was incorrectly replaced!\nOriginal:\n{content}\nTransformed:\n{transformed}")

def test_both_changes():
    print("\nTesting Both FN change and Deduplication...")
    # 1. FN is a phone number and is redundant -> should be replaced by ORG
    # 2. There is a duplicate ADR line -> should be de-duplicated
    content = "BEGIN:VCARD\nFN:+4912345\nORG:MyCompany\nTEL:+4912345\nADR:123 St\nADR:123 St\nEND:VCARD"
    
    # We need to mock the dry-run reporting in a test. 
    # Since we can't easily call batch_process_vcards with a string, 
    # we'll just check the transformed content and manually verify the logic.
    transformed = vcf_cleaner.transform_vcard_content(content)
    
    # Check FN change
    old_fn = vcf_cleaner.extract_fn_value(content)
    new_fn = vcf_cleaner.extract_fn_value(transformed)
    fn_changed = (old_fn != new_fn)
    
    # Check Deduplication
    content_lines = content.splitlines()
    transformed_lines = transformed.splitlines()
    def get_rest(lines): return [l for l in lines if not l.startswith("FN:")]
    dedup_happened = (get_rest(content_lines) != get_rest(transformed_lines))

    print(f"  FN changed: {fn_changed} ({old_fn} -> {new_fn})")
    print(f"  Deduplication happened: {dedup_happened}")

    if fn_changed and dedup_happened:
        print("  SUCCESS: Both changes detected.")
    else:
        print("  FAILED: One or both changes were not detected correctly.")

if __name__ == "__main__":
    test_address_as_fn()
    test_both_changes()
