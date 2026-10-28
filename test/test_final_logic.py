import importlib.util
import os
import re

spec = importlib.util.spec_from_file_location("vcf_cleaner", "vcf-cleaner.py")
vcf_cleaner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vcf_cleaner)

def test_fn_anywhere_logic():
    print("Testing FN address matches ANY line (not just ADR)...")
    # FN address matches a custom field X-ADDR, not ADR
    content = "BEGIN:VCARD\nFN:Mainstr. 16\nORG:Sample Org\nX-ADDR:Mainstr. 16\nEND:VCARD"
    
    transformed = vcf_cleaner.transform_vcard_content(content)
    old_fn = vcf_cleaner.extract_fn_value(content)
    new_fn = vcf_cleaner.extract_fn_value(transformed)
    
    if old_fn == "Mainstr. 16" and new_fn == "Sample Org":
        print("  SUCCESS: FN replaced because address was found in X-ADDR.")
    else:
        print(f"  FAILED: Expected FN 'Sample Org', got '{new_fn}' (Old FN: '{old_fn}')")
        print(f"Transformed content:\n{transformed}")

def test_n_adr_logic():
    print("\nTesting N vs ADR removal (independent of FN logic)...")
    # FN is a name (not an address)
    # N is an address matching ADR
    # ORG is present
    content = "BEGIN:VCARD\nFN:John Doe\nN:Mainstr. 16\nORG:Sample Org\nADR:Mainstr. 16\nEND:VCARD"
    
    transformed = vcf_cleaner.transform_vcard_content(content)
    
    fn_ok = (vcf_cleaner.extract_fn_value(transformed) == "John Doe")
    n_gone = "N:Mainstr. 16" not in transformed
    
    if fn_ok and n_gone:
        print("  SUCCESS: N removed because it matched ADR, even though FN was not replaced.")
    else:
        print(f"  FAILED: FN ok: {fn_ok}, N ok: {n_gone}")
        print(f"Transformed content:\n{transformed}")

def test_combined_logic():
    print("\nTesting Combined Logic (FN address matches ANY, N matches ADR)...")
    content = "BEGIN:VCARD\nFN:Mainstr. 16\nN:Mainstr. 16\nORG:Sample Org\nADR:Mainstr. 16\nEND:VCARD"
    
    transformed = vcf_cleaner.transform_vcard_content(content)
    old_fn = vcf_cleaner.extract_fn_value(content)
    new_fn = vcf_cleaner.extract_fn_value(transformed)
    
    fn_ok = (old_fn == "Mainstr. 16" and new_fn == "Sample Org")
    n_gone = "N:Mainstr. 16" not in transformed
    
    if fn_ok and n_gone:
        print("  SUCCESS: FN replaced and N removed.")
    else:
        print(f"  FAILED: FN ok: {fn_ok}, N ok: {n_gone}")
        print(f"Transformed content:\n{transformed}")

if __name__ == "__main__":
    test_fn_anywhere_logic()
    test_n_adr_logic()
    test_combined_logic()
