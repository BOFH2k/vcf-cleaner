# Agent Instructions for vCardCleaner

## Project Overview
A single-file Python utility to clean VCard files by replacing the `FN` (Full Name) field with the `ORG` (Organization) field if `FN` contains a phone number that is already present elsewhere in the VCard.

## Execution
The script is run via Python:
```bash
python vcf-cleaner.py <input_dir> <output_dir> [options]
```

### Important Options
- `-d`, `--dry-run`: **Highly recommended.** Performs a simulation and prints what would be changed without writing any files.
- `--[no-]strip-invisible` (default: on): Remove zero-width/invisible characters (e.g. U+200B ZWSP, BOM) that render like extra spaces. Disable with `--no-strip-invisible` to keep them.
- `--[no-]dedup` (default: on): Remove duplicate lines. Disable with `--no-dedup` to keep them.
- `--workers N` (default: 1): Process files in parallel with up to N threads. Only helps on very large inputs; per-file work is tiny and CPU-bound, so threading is opt-in.

## Testing
The `test/` directory contains standard-library `unittest` tests with inline VCard data. Run the full suite from the repo root:
```bash
python -m unittest discover -s test -v
```

To verify functionality against real-world data, use the sample VCard files in `example/` (they are local test data and are **not** tracked in git):

1. **Dry Run**:
   ```bash
   python vcf-cleaner.py example/ test_output/ --dry-run
   ```
2. **Actual Execution**:
   ```bash
   python vcf-cleaner.py example/ test_output/
   ```
3. **Verification**: Compare the original files in `example/` with the processed files in `test_output/` to ensure `FN` fields have been correctly updated.

## Git and Environment
To prevent accidental leakage of test data, the `example/` (sample VCards) and `test_output/` directories are explicitly ignored in `.gitignore`. The `test/` directory contains test programs and is tracked.

## Notes
- No external dependencies are required (uses standard library).
