
import importlib.util
import sys

# Load vcf-cleaner.py manually due to hyphen
spec = importlib.util.spec_from_file_location("vcf_cleaner", "vcf-cleaner.py")
vcf_cleaner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vcf_cleaner)

# Test 1: Content with trailing newline
# Before, this would always return True (changed) because of .strip()
content_with_newline = "FN:John\nORG:Company\n"
transformed_with_newline = vcf_cleaner.transform_vcard_content(content_with_newline)
print(f"Test 1 (with newline):")
print(f"Changed: {transformed_with_newline != content_with_newline}")
print(f"Original repr: {repr(content_with_newline)}")
print(f"Transformed repr: {repr(transformed_with_newline)}")

print("-" * 20)

# Test 2: Content without trailing newline
content_no_newline = "FN:John\nORG:Company"
transformed_no_newline = vcf_cleaner.transform_vcard_content(content_no_newline)
print(f"Test 2 (no newline):")
print(f"Changed: {transformed_no_newline != content_no_newline}")
print(f"Original repr: {repr(content_no_newline)}")
print(f"Transformed repr: {repr(transformed_no_newline)}")
