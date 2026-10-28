import importlib.util
import sys

# Load vcf-cleaner.py manually due to hyphen
spec = importlib.util.spec_from_file_location("vcf_cleaner", "vcf-cleaner.py")
vcf_cleaner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vcf_cleaner)

# Test ADR deduplication bug
# We expect 4 identical ADR lines to be de-duplicated into 1 line.
content_adr = "FN:John\nADR:123 Main St\nADR:123 Main St\nADR:123 Main St\nADR:123 Main St"
transformed_adr = vcf_cleaner.transform_vcard_content(content_adr)
lines = transformed_adr.splitlines()
adr_lines = [l for l in lines if l.startswith("ADR")]

print(f"Input ADR lines: 4")
print(f"Output ADR lines: {len(adr_lines)}")
print(f"Output lines: {repr(transformed_adr)}")

if len(adr_lines) != 1:
    print("BUG DETECTED: ADR lines were not correctly de-duplicated!")
else:
    print("ADR lines de-duplicated correctly.")
