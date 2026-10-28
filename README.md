# vCard Cleaner

A simple Python utility to clean VCard (`.vcf`) files by replacing the `FN` (Full Name) field with the `ORG` (Organization) field when the `FN` field contains a phone number that is already present in another field of the VCard.

## Features

- **Redundancy Reduction**: Automatically detects if `FN` is a phone number and if that number exists elsewhere in the card.
- **Safe Execution**: Includes a `--dry-run` mode to preview changes before they are applied.
- **Zero Dependencies**: Uses only the Python standard library.

## Installation

No installation is required. Simply ensure you have Python 3 installed.

## Usage

Run the script from your terminal:

```bash
python vcf-cleaner.py <input_dir> <output_dir> [options]
```

### Arguments

- `input_dir`: The directory containing the source `.vcf` files.
- `output_dir`: The directory where the cleaned `.vcf` files will be saved.

### Options

- `-d`, `--dry-run`: Performs a simulation. It will print which files would be changed and show the transformation (e.g., `FN: 'old' --> 'new'`) without writing any actual files to disk.
- `--[no-]strip-invisible` (default: on): Remove zero-width/invisible characters (e.g. U+200B ZWSP, BOM) that render like extra spaces. Disable with `--no-strip-invisible` to keep them.
- `--[no-]dedup` (default: on): Remove duplicate lines. Disable with `--no-dedup` to keep them.
- `--workers N` (default: 1): Process files in parallel with up to N threads. Only helps on very large inputs; per-file work is tiny and CPU-bound, so threading is opt-in.

### Example

**Dry run (preview only):**
```bash
python vcf-cleaner.py ./contacts_raw ./contacts_cleaned --dry-run
```

**Actual processing:**
```bash
python vcf-cleaner.py ./contacts_raw ./contacts_cleaned
```

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.
