# vCard Cleaner

A simple Python utility to clean VCard (`.vcf`) files by replacing the `FN` (Full Name) field with the `ORG` (Organization) field when `FN` holds redundant content — a phone number, an address or an e-mail address that is already recorded elsewhere in the card. It also tidies duplicated lines and normalizes the file's line structure.

## Features

- **Redundant `FN` → `ORG`**: `FN` is rewritten to the `ORG` value (only when `ORG` is not empty) when it duplicates content that exists elsewhere in the card:
  - **Phone**: `FN` is just a phone number and the same number appears in another field; separators (spaces, dots, dashes, parentheses) are ignored, so `+34 933-173 022` matches `+34933173022`.
  - **Address**: `FN` mixes letters and digits and its words match another field's value in any order, ignoring punctuation, so `Mainstr. 16` matches `16 Mainstr`. Word identity is preserved, so `ABC 123` does not match `321 CBA`.
  - **E-mail**: `FN` is an e-mail address that also appears in another field (compared case-insensitively).
- **Name cleanup**: an `N` line that only repeats the `ADR` address (same words, any order) is removed, as is an `N` line that holds nothing but a phone number matching a `TEL` value (separators ignored). An `N` that also repeats an `EMAIL` value has just that e-mail cut out of it (the whole `N` line is dropped when nothing else is left in it). An `N` that contains a real name is never removed by the address/phone rules.
- **Property-aware parsing**: property names are matched case-insensitively and may carry parameters or a group prefix (e.g. `item1.FN;LANGUAGE=en`); that prefix and its parameters are kept when `FN` is rewritten.
- **VCard line handling**: folded (continuation) lines in the input are unfolded before processing; output lines are re-folded to at most 75 bytes per line and saved with CRLF line endings, as required by the VCard format. Multi-byte characters are never split across lines.
- **Invisible characters**: zero-width characters (ZWSP, ZWNJ, ZWJ, word-joiner, BOM) that look like extra spaces are removed, and whitespace inside `FN` is collapsed to single spaces (toggle with `--strip-invisible` / `--no-strip-invisible`).
- **Deduplication**: after the logical lines are unfolded, exact duplicate lines are dropped (keep the first occurrence only; toggle with `--dedup` / `--no-dedup`).
- **Safe Execution**: `--dry-run` previews changes without writing anything, and reports per file whether `FN` was changed, deduplication was applied, or only line re-wrapping was applied.
- **Failure reporting**: unreadable or unwritable files are reported individually, counted in the summary, and make the command exit with a non-zero status.
- **Parallel processing**: opt-in `--workers` speeds up large directories.
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

## Tests

Run the standard-library test suite from the repository root:

```bash
python -m unittest discover -s test -v
```
