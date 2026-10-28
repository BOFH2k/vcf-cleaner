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
- `--[no-]blank-n` (default: off): Keep a removed `N` line as the empty `N:;;;;` instead of dropping it (RFC 2426 mandates `N` and allows all-empty sub-fields).
- `--workers N` (default: 1): Process files in parallel with up to N threads. Only helps on very large inputs; per-file work is tiny and CPU-bound, so threading is opt-in.
- `--validate` (default: off): Check each resulting vCard (in a dry run, the one that would be written) and report invalid ones as `[INVALID OUTPUT] <file>` plus a `Files with invalid output:` count. Structural rules need no dependency; `vobject` is an optional second tier. Ask for it on an interpreter that cannot import `vobject` and the run prints the bootstrap below and exits `1`.
- `--validate-ical` (default: off): Also ask `icalendar`, which is stricter than VCard 3.0 (`N`/`ADR` sub-field counts, single card per file), so it can flag cards a VCard 3.0 reader accepts. Opt-in extra tier; requires `--validate`.

### Exit codes
`0` success; `1` the run itself failed (bad input directory, unreadable file, or `--validate` without its library); `2` at least one invalid output vCard.

### Virtual environments
There are two separate `uv` virtual environments and **they must never be shared, reused, renamed or merged into one another**:

| Directory | Owner | Documented in | Used by |
| --- | --- | --- | --- |
| `.venv` | the **user's** environment | `README.md` | the user, following the README bootstrap |
| `.venv-opencode` | the **coding agent's** environment | this file (`AGENTS.md`) | every command you run |

Never run a command against `.venv`, never create or modify `.venv`, and never print its contents: it belongs to the user and only `README.md` describes it. Always use `.venv-opencode` for the bootstrap and for the library-tier test/`--validate` runs below. Both directories are gitignored.

### Validation bootstrap
The script is standard-library only. The validator libraries are installed out-of-band in the agent venv `.venv-opencode` and imported lazily inside `validate_vcard`, never at module level (a top-level import would break `test/helpers.py`, which loads the script with `importlib`):
```bash
uv venv .venv-opencode --python 3.14
uv pip install --python .venv-opencode vobject   # + icalendar for --validate-ical
.venv-opencode/bin/python vcf-cleaner.py example/ test_output/ --validate
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
4. **Validation**: with the agent venv interpreter (`.venv-opencode/bin/python`, never `.venv`), re-run with `--validate` (and `--validate-ical`) and confirm `Files with invalid output: 0`.

The library-tier tests in `test/test_regressions.py` are skipped on an interpreter that lacks `vobject`/`icalendar`, so run the suite twice to cover everything:
```bash
python -m unittest discover -s test -v                  # library tiers skipped
.venv-opencode/bin/python -m unittest discover -s test -v   # library tiers exercised (agent venv, never .venv)
```

## Git and Environment
To prevent accidental leakage of test data, the `example/` (sample VCards) and `test_output/` directories are explicitly ignored in `.gitignore`. The `test/` directory contains test programs and is tracked.

Both virtual environments, `.venv` (the user's) and `.venv-opencode` (the agent's), are gitignored as well. Keep them separate: `.venv` is the user's environment and is documented only in `README.md`; as a coding agent, work only in `.venv-opencode` and do not adopt, convert or share `.venv`.

**Never quote or copy data from `example/` into anything that is tracked: not into code comments, not into tests (use generic synthetic vCards such as `Sample Org` / `+49123456789`), and not into commit messages, PR text, or issue reports.** The same applies to data derived from those files, such as personal names, addresses, e-mail values, and real phone numbers. Probes and scratch scripts that read `example/` must print counts only, never content, and stay untracked (use `/tmp/opencode`).

## Notes
- The dry-run report names the rule that actually fired for each changed file (`[FN replaced by ORG]`, `[N line removed]` / `[N line blanked]`, `[N line cleaned]`, `[Invisible characters removed]`, `[Duplicate lines removed]`, falling back to `[Line re-wrapping applied]`). `transform_vcard_content` keeps its public signature and delegates to `transform_vcard_with_labels`, which also returns those labels; the redundancy rules themselves live in `redundancy_decisions`.
- No external dependencies are required (uses standard library). The optional `--validate` checker (`vobject`, and `icalendar` for `--validate-ical`) is the only exception, and it is installed out-of-band in the agent venv `.venv-opencode` rather than imported by the script.
