# vCard Cleaner

A simple Python utility to clean VCard (`.vcf`) files by replacing the `FN` (Full Name) field with the `ORG` (Organization) field when `FN` holds redundant content — a phone number, an address or an e-mail address that is already recorded elsewhere in the card. It also tidies duplicated lines and normalizes the file's line structure.

## Features

- **Redundant `FN` → `ORG`**: `FN` is rewritten to the `ORG` value (only when `ORG` is not empty) when it duplicates content that exists elsewhere in the card:
  - **Phone**: `FN` is just a phone number and the same number appears in another field; separators (spaces, dots, dashes, parentheses) are ignored, so `+34 933-173 022` matches `+34933173022`.
  - **Address**: `FN` mixes letters and digits and its words match another field's value in any order, ignoring punctuation, so `Mainstr. 16` matches `16 Mainstr`. Word identity is preserved, so `ABC 123` does not match `321 CBA`.
  - **E-mail**: `FN` is an e-mail address that also appears in another field (compared case-insensitively).
- **Name cleanup**: an `N` line that only repeats the `ADR` address (same words, any order) is removed, as is an `N` line that holds nothing but a phone number matching a `TEL` value (separators ignored). An `N` that repeats an `EMAIL` value has just that e-mail cut out of it (the whole `N` line is dropped when nothing else is left in it) — this also covers e-mails that a name parser split into `N`'s sub-fields, e.g. `N:de;info@example;;;` for `EMAIL:info@example.de` (e-mails with letters outside ASCII count too). The same holds for Internet addresses: an `N` that spells `www` or `http` and whose words match a URL-valued other field (a `URL` property, or e.g. an `EMAIL` holding `www.sample-org.de`) is removed, e.g. `N:de;www;sample-org.;;` for `www.sample-org.de`. An `N` holding a real name is never removed: only an exact token match counts, so `N:Mustermann;Thomas;;;` survives next to `EMAIL:thomas.mustermann@example.com`.
- **Property-aware parsing**: property names are matched case-insensitively and may carry parameters or a group prefix (e.g. `item1.FN;LANGUAGE=en`); that prefix and its parameters are kept when `FN` is rewritten.
- **VCard line handling**: folded (continuation) lines in the input are unfolded before processing; output lines are re-folded to at most 75 bytes per line and saved with CRLF line endings, as required by the VCard format. Multi-byte characters are never split across lines.
- **Invisible characters**: zero-width characters (ZWSP, ZWNJ, ZWJ, word-joiner, BOM) that look like extra spaces are removed, and whitespace inside `FN` is collapsed to single spaces (toggle with `--strip-invisible` / `--no-strip-invisible`).
- **Deduplication**: after the logical lines are unfolded, exact duplicate lines are dropped (keep the first occurrence only; toggle with `--dedup` / `--no-dedup`).
- **Safe Execution**: `--dry-run` previews changes without writing anything, and reports per file what actually fired: the `FN` rewrite shown as old → new value, plus a label for each rule that changed something (`[FN replaced by ORG]`, `[N line removed]` or `[N line blanked]`, `[N line cleaned]`, `[Invisible characters removed]`, `[Duplicate lines removed]`, or `[Line re-wrapping applied]` when only the line structure changed).
- **Failure reporting**: unreadable or unwritable files are reported individually, counted in the summary, and make the command exit with a non-zero status.
- **Parallel processing**: opt-in `--workers` speeds up large directories.
- **Zero Dependencies**: Uses only the Python standard library. Validation is the only exception, and it degrades gracefully when the optional checker library is missing (see [Validating the output](#validating-the-output)).

## Installation

No installation is required. Simply ensure you have Python 3 installed.

The optional `--validate` checker is the only part that is not standard library. It is kept out of the script's own imports and installed separately, in a [uv](https://docs.astral.sh/uv/)-managed virtual environment, so the cleaner itself never depends on it:

```bash
uv venv .venv --python 3.14
uv pip install --python .venv vobject
```

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
- `--[no-]blank-n` (default: off): When a fully redundant `N` line would be dropped, keep it as the empty `N:;;;;` instead. VCard 3.0 (RFC 2426) mandates the `N` property and its ABNF allows all five sub-fields to be empty; VCard 4.0 only recommends `N`, so dropping it stays the information-preserving default.
- `--workers N` (default: 1): Process files in parallel with up to N threads. Only helps on very large inputs; per-file work is tiny and CPU-bound, so threading is opt-in.
- `--validate` (default: off): Check each resulting vCard and print the invalid ones under `[INVALID OUTPUT] <file>`, with one indented reason per problem, plus a `Files with invalid output:` count in the summary. Works in a dry run too (it checks what would be written). Needs the `vobject` library; run it with the interpreter that has it (see below).
- `--validate-ical` (default: off): Also ask [icalendar](https://pypi.org/project/icalendar/), which is stricter than VCard 3.0 — it insists that `N` and `ADR` carry their full sub-field counts and that a file holds a single card — so it can flag cards that a VCard 3.0 reader accepts. It is an extra tier, not the gate, and requires `--validate`.

### Validating the output

`--validate` layers the checks it can run on top of each other:

1. **Structural rules that need no library** (always on): physical lines stay within 75 bytes, line endings are plain CRLF pairs, every content line is a `NAME[;params]:value` property (or a continuation) with a VCard-legal name, only printable characters and legal escapes, parameter quotes are closed, and `BEGIN:`/`END:` markers are paired. It also reports more than one `FN` in a card.
2. **`vobject` as a second tier**, which adds value-level checks (for example an unterminated parameter quote in a property header).
3. **`icalendar` as an opt-in third tier** with `--validate-ical`, as described above.

Run it with the interpreter that can import the checker — either the venv you bootstrapped above, or in one go with `uv run`:

```bash
.venv/bin/python vcf-cleaner.py ./contacts_raw ./contacts_cleaned --validate
uv run --with vobject vcf-cleaner.py ./contacts_raw ./contacts_cleaned --validate
```

If you ask for `--validate` on an interpreter that cannot import `vobject`, the command does not quietly skip the check: it prints the exact setup instructions and exits with status `1`. The validation function itself keeps the library import optional, so calling it from another script on a plain interpreter still runs every rule that needs no dependency.

### Exit codes

- `0`: the run completed and nothing was wrong.
- `1`: the run itself failed (unreadable input directory, a file that could not be processed, or `--validate` requested without its library).
- `2`: at least one resulting vCard was reported invalid. This is a distinct status so a caller can tell "the run broke" from "the output is not a valid vCard".

### Example

**Dry run (preview only):**
```bash
python vcf-cleaner.py ./contacts_raw ./contacts_cleaned --dry-run
```

**Actual processing:**
```bash
python vcf-cleaner.py ./contacts_raw ./contacts_cleaned
```

**Process and check the result:**
```bash
.venv/bin/python vcf-cleaner.py ./contacts_raw ./contacts_cleaned --validate
```

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for more information.

## Tests

Run the standard-library test suite from the repository root:

```bash
python -m unittest discover -s unittests -v
```

The tests that exercise the `vobject` and `icalendar` tiers are skipped when those libraries are not importable. Run them a second time with the venv interpreter to cover that code as well:

```bash
.venv/bin/python -m unittest discover -s unittests -v
```

This `.venv` is your own environment and is the only one these instructions describe. A coding agent working in this repository keeps its own, separate environment in `.venv-opencode`; the two are never shared, so please do not point one at the other or reuse it.
