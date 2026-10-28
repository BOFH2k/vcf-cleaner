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

## Notes
- No external dependencies are required (uses standard library).
