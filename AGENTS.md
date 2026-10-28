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
- `--validate` (default: off): Check each resulting vCard (in a dry run, the one that would be written) and report invalid ones as `[INVALID OUTPUT] <file>` plus a `Files with invalid output:` count. Structural rules need no dependency; `vobject` is an optional second tier. Ask for it on an interpreter that cannot import `vobject` and the run prints the bootstrap below and exits `1`.
- `--validate-ical` (default: off): Also ask `icalendar`, which is stricter than VCard 3.0 (`N`/`ADR` sub-field counts, single card per file), so it can flag cards a VCard 3.0 reader accepts. Opt-in extra tier; requires `--validate`.

### Exit codes
`0` success; `1` the run itself failed (bad input directory, unreadable file, or `--validate` without its library); `2` at least one invalid output vCard.

### Validation bootstrap
The script is standard-library only. The validator libraries are installed out-of-band in a `uv` venv and imported lazily inside `validate_vcard`, never at module level (a top-level import would break `test/helpers.py`, which loads the script with `importlib`):
```bash
uv venv .venv --python 3.14
uv pip install --python .venv vobject
.venv/bin/python vcf-cleaner.py example/ test_output/ --validate
# or, in one go: uv run --with vobject vcf-cleaner.py example/ test_output/ --validate
```

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
4. **Validation**: with the `uv` venv interpreter, re-run with `--validate` (and `--validate-ical`) and confirm `Files with invalid output: 0`.

The library-tier tests in `test/test_regressions.py` are skipped on an interpreter that lacks `vobject`/`icalendar`, so run the suite twice to cover everything:
```bash
python -m unittest discover -s test -v        # library tiers skipped
.venv/bin/python -m unittest discover -s test -v   # library tiers exercised
```

## Git and Environment
To prevent accidental leakage of test data, the `example/` (sample VCards) and `test_output/` directories are explicitly ignored in `.gitignore`. The `test/` directory contains test programs and is tracked.

**Never quote or copy data from `example/` into anything that is tracked: not into code comments, not into tests (use generic synthetic vCards such as `Sample Org` / `+49123456789`), and not into commit messages, PR text, or issue reports.** The same applies to data derived from those files, such as personal names, addresses, e-mail values, and real phone numbers. Probes and scratch scripts that read `example/` must print counts only, never content, and stay untracked (use `/tmp/opencode`).

## Notes
- No external dependencies are required (uses standard library). The optional `--validate` checker (`vobject`, and `icalendar` for `--validate-ical`) is the only exception, and it is installed in a `uv` venv rather than imported by the script.
