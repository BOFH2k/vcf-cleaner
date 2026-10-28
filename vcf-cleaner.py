import re
import os
import argparse
import importlib.util
from concurrent.futures import ThreadPoolExecutor

MAX_LINE_BYTES = 75
INVISIBLE_RE = re.compile(r'[\u200b\u200c\u200d\u2060\ufeff]')
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
NONPHONE_RE = re.compile(r'[^\d+]')
PHONE_RE = re.compile(r'^\+?\d+$')
WS_RE = re.compile(r'\s+')
EMPTY_PAREN_RE = re.compile(r'\(\s*\)')

def normalize_phone(text):
    """
    Extracts only digits and the plus sign from a string.
    Example: '+34 933-173 022' -> '+34933173022'
    """
    if not text:
        return ""
    return NONPHONE_RE.sub('', text)

def normalize_content(text):
    """Normalize alphanumeric tokens for order-independent address comparison.

    Sorting whole tokens allows harmless word-order and punctuation differences
    without making unrelated strings such as ``ABC 123`` and ``321 CBA`` equal.
    """
    if not text:
        return ()
    return tuple(sorted(re.findall(r'[a-zA-Z0-9]+', text.lower())))

def get_property(line):
    """Return a case-normalized vCard property name, or None.

    Property names are case-insensitive. A group prefix (for example,
    ``item1.FN``) is not part of the property name.
    """
    if ":" not in line:
        return None
    name = line.split(":", 1)[0].split(";", 1)[0]
    return name.rsplit(".", 1)[-1].upper()

def strip_invisible(text):
    """
    Removes zero-width and invisible characters (which render like extra spaces
    but are not matched by \\s in regular expressions).
    Example: 'Jane \u200b Doe' -> 'Jane  Doe'
    """
    if not text:
        return ""
    return INVISIBLE_RE.sub('', text)

def collapse_spaces(text, strip_inv=True):
    """
    Collapses runs of whitespace into a single space and trims the ends.
    If strip_inv is True, invisible characters are removed first.
    Example: 'Jane \u200b Doe ' -> 'Jane Doe'
    """
    if not text:
        return ""
    if strip_inv:
        text = strip_invisible(text)
    return WS_RE.sub(' ', text).strip()

def unfold_lines(lines):
    """
    Merges VCard continuation lines into the logical line they belong to.
    A physical line starting with a space or tab is a continuation of the
    previous line; the leading whitespace character is removed on unfolding.
    """
    unfolded = []
    for line in lines:
        if unfolded and line[:1] in (' ', '\t'):
            unfolded[-1] += line[1:]
        else:
            unfolded.append(line)
    return unfolded

def fold_line(line, max_bytes=MAX_LINE_BYTES):
    """
    Splits a logical line into physical VCard lines of at most max_bytes bytes.
    Continuation lines start with a single space. Folding splits on byte
    boundaries (multi-byte characters are never split).
    """
    if len(line.encode('utf-8')) <= max_bytes:
        return [line]
    parts = []
    current = []
    current_bytes = 0
    for ch in line:
        ch_bytes = len(ch.encode('utf-8'))
        if current_bytes + ch_bytes > max_bytes:
            parts.append(''.join(current))
            current = [' ']
            current_bytes = 1
        current.append(ch)
        current_bytes += ch_bytes
    parts.append(''.join(current))
    return parts

def dedup_lines(lines):
    """Returns the lines keeping only the first occurrence of each line."""
    seen = set()
    unique = []
    for line in lines:
        if line not in seen:
            unique.append(line)
            seen.add(line)
    return unique

def parse_fields(lines):
    """
    Collects the VCard properties relevant to the redundancy rules.
    Returns {'FN': (idx, value), 'N': (idx, value), 'ORG': (idx, value), 'ADR': (idx, value)}
    where idx is the line index of the (last) occurrence, or (-1, None) if absent.
    """
    fields = {"FN": (-1, None), "N": (-1, None), "ORG": (-1, None), "ADR": (-1, None)}
    for i, line in enumerate(lines):
        prop = get_property(line)
        if prop in fields:
            fields[prop] = (i, line.split(":", 1)[1].strip())
    return fields

def phone_like(fn_val):
    """Returns the normalized phone form of the text if it is phone-like, else None."""
    fn_norm = normalize_phone(fn_val)
    if PHONE_RE.match(fn_norm) is not None and len(fn_norm) > 3 \
           and not any(c.isalpha() for c in fn_val):
        return fn_norm
    return None

def address_like(fn_val):
    """Returns the order-independent content form if the text has letters
    and digits (address-like), else None."""
    if not (any(c.isalpha() for c in fn_val) and any(c.isdigit() for c in fn_val)):
        return None
    return normalize_content(fn_val) or None

def precompute_other(lines, fn_idx, need_phones=True, need_contents=True, need_emails=True):
    """
    Precomputes the normalized forms of every line except the FN line, once,
    so the redundancy checks can run as O(1) set lookups instead of
    re-normalizing all lines per rule. Sets for rules that do not apply to
    FN (need_* flag False) are left empty and never built.
    Returns (phones, contents, emails):
    - phones:   set of normalize_phone(line)
    - contents: set of normalized token tuples for every line with a ':'
    - emails:   set of lowercased e-mails found in any line
    """
    phones = set()
    contents = set()
    emails = set()
    for i, line in enumerate(lines):
        if i == fn_idx:
            continue
        if need_phones:
            phones.add(normalize_phone(line))
        if need_contents:
            parts = line.split(":", 1)
            if len(parts) > 1:
                contents.add(normalize_content(parts[1].strip()))
        if need_emails:
            emails.update(e.lower() for e in EMAIL_RE.findall(line))
    return phones, contents, emails

def is_redundant_phone(fn_val, other_phones):
    """True if FN is a phone number and the same number appears in another line
    (via the precomputed set other_phones)."""
    fn_norm = phone_like(fn_val)
    return fn_norm is not None and fn_norm in other_phones

def is_redundant_email(fn_val, other_emails):
    """True if FN contains an e-mail address that also appears in another line
    (via the precomputed set other_emails)."""
    fn_emails = set(e.lower() for e in EMAIL_RE.findall(fn_val))
    if not fn_emails:
        return False
    return bool(fn_emails & other_emails)

def is_redundant_address(fn_val, other_contents):
    """True if FN has letters and digits and its content (order-independent)
    also appears as the value of another line (via the precomputed set
    other_contents)."""
    fn_norm = address_like(fn_val)
    return fn_norm is not None and fn_norm in other_contents

def is_n_redundant_with_adr(n_val, adr_val):
    """True if N holds address info that matches ADR (order-independent).
    A phone-valued N is never considered redundant with ADR."""
    if not (n_val and adr_val):
        return False
    is_address_format = (any(c.isalpha() for c in n_val)
                         and any(c.isdigit() for c in n_val))
    if not is_address_format:
        return False
    n_norm = normalize_content(n_val)
    return bool(n_norm) and n_norm == normalize_content(adr_val)

def is_n_redundant_with_tel(n_val, tel_phones):
    """True if N holds only a phone number (no letters, e.g. ';+49123;;;')
    whose normalized form matches one of the TEL values (tel_phones set).
    An N with letters is a real name and never removed by this rule."""
    if not n_val or not tel_phones or any(c.isalpha() for c in n_val):
        return False
    n_norm = phone_like(n_val)
    return n_norm is not None and n_norm in tel_phones

def tel_phone_forms(lines):
    """Normalized phone forms of every TEL value in the lines."""
    return {normalize_phone(line.split(":", 1)[1])
            for line in lines if get_property(line) == "TEL"}

def email_value_forms(lines):
    """Lowercased e-mails found in every EMAIL value in the lines."""
    return {e.lower()
            for line in lines if get_property(line) == "EMAIL"
            for e in EMAIL_RE.findall(line)}

def strip_redundant_emails(value, email_values):
    """Returns value with e-mails that duplicate an EMAIL line removed
    (including now-empty parentheses), or None if nothing was removed."""
    stripped = EMAIL_RE.sub(
        lambda m: '' if m.group(0).lower() in email_values else m.group(0),
        value)
    if stripped == value:
        return None
    stripped = EMPTY_PAREN_RE.sub('', stripped)
    return stripped

def email_token_forms(lines):
    """Order-independent token forms of every EMAIL value in the lines.

    The whole value is tokenized, not just the part EMAIL_RE recognizes, so
    that e-mails with non-ASCII letters (spícefrankfurt@yahoo.de) still match
    an N built from the same pieces.
    """
    return {normalize_content(line.split(":", 1)[1])
            for line in lines
            if get_property(line) == "EMAIL" and "@" in line}

def is_n_only_split_email(n_val, email_tokens):
    """True if N holds nothing but the pieces of an e-mail that a name parser
    split across its sub-fields, moving the domain ending to the front
    (e.g. 'de;info@example;;;'). The tokens must match an e-mail value exactly,
    so a real name is never removed even when an EMAIL repeats it
    (N 'Merkle;Thomas;;;' vs EMAIL thomas.merkle@sva.de)."""
    if "@" not in n_val:
        return False
    n_tokens = normalize_content(n_val)
    return bool(n_tokens) and n_tokens in email_tokens


def extract_fn_value(vcard_text):
    """Returns the FN value of a vCard (unfolded), for dry-run display."""
    for line in unfold_lines(vcard_text.splitlines()):
        if get_property(line) == "FN":
            return line.split(":", 1)[1].strip()
    return "Unknown"

def apply_changes(lines, fields, replace_fn, remove_n, strip_inv, n_new_val=None,
                  blank_n=False):
    """Returns the lines with FN replaced by ORG and/or N removed or rewrites
    to n_new_val (N line kept with its e-mail content cleaned out). With
    blank_n a removed N line is kept as the empty 'N:;;;;' instead.
    A kept FN line's value is whitespace-normalized (its property prefix is kept)."""
    fn_idx = fields["FN"][0]
    n_idx = fields["N"][0]
    new_lines = []
    for i, line in enumerate(lines):
        if i == n_idx:
            if remove_n:
                if blank_n:
                    prop_part = line.split(":", 1)[0]
                    new_lines.append(f"{prop_part}:;;;;")
                continue
            if n_new_val is not None:
                prop_part = line.split(":", 1)[0]
                new_lines.append(f"{prop_part}:{n_new_val}")
            else:
                new_lines.append(line)
            continue
        if i == fn_idx:
            if replace_fn:
                org_val = fields["ORG"][1]
                prop_part = line.split(":", 1)[0]
                new_lines.append(
                    f"{prop_part}:{collapse_spaces(org_val, strip_inv=strip_inv)}")
            else:
                prop_part = line.split(":", 1)[0]
                fn_value = collapse_spaces(line.split(":", 1)[1], strip_inv=strip_inv) if ":" in line else ""
                new_lines.append(f"{prop_part}:{fn_value}")
        else:
            new_lines.append(line)
    return new_lines

def transform_vcard_content(vcard_text, strip_inv=True, dedup=True, blank_n=False):
    """
    Transforms a vCard based on redundancy logic and performs line-level deduplication.

    Input continuation lines are unfolded first; output is re-folded to at most
    75 bytes per line and written with CRLF line endings (VCard spec).

    Redundancy logic:
    1. Is FN a phone number?
    2. If yes: Does this number (normalized) exist exactly as is in another field?
    3. If yes: Replace FN with ORG.
    4. Is FN an address?
    5. If yes: Does this address exist anywhere else in the vCard (order-independent)?
    6. If yes: Replace FN with ORG.
    7. Is FN an e-mail address? If that address exists elsewhere in the vCard: Replace FN with ORG.
    8. Additionally, if N contains address info that matches ADR, remove N.
    9. If N holds nothing but a phone number that matches a TEL value, remove N.
    10. If N holds an e-mail that matches an EMAIL value, remove that e-mail from
        N (and the whole N line when nothing but the e-mail remains in it); the
        e-mail may also have been split into N's sub-fields by a name parser,
        e.g. 'de;info@example;;;' for the EMAIL 'info@example.de'.

    Deduplication logic:
    Perform line-level deduplication (enabled by the dedup flag).

    The strip_inv flag enables removal of zero-width/invisible characters;
    the dedup flag enables line-level deduplication. The blank_n flag keeps a
    removed N line as the empty 'N:;;;;' instead of dropping it: VCard 3.0
    (RFC 2426) mandates the N property and its ABNF allows all five sub-fields
    to be empty.
    """
    lines = unfold_lines(vcard_text.split('\n'))
    if strip_inv:
        lines = [strip_invisible(line) for line in lines]

    fields = parse_fields(lines)
    fn_idx, fn_val = fields["FN"]

    replace_fn = False
    if fn_val is not None:
        need_phones = phone_like(fn_val) is not None
        need_addr = address_like(fn_val) is not None
        need_email = EMAIL_RE.search(fn_val) is not None
        if need_phones or need_addr or need_email:
            other_phones, other_contents, other_emails = precompute_other(
                lines, fn_idx, need_phones, need_addr, need_email)
            redundant = (is_redundant_phone(fn_val, other_phones)
                         or is_redundant_address(fn_val, other_contents)
                         or is_redundant_email(fn_val, other_emails))
            replace_fn = redundant and bool(fields["ORG"][1])

    remove_n = is_n_redundant_with_adr(fields["N"][1], fields["ADR"][1])
    n_new_val = None
    if not remove_n and phone_like(fields["N"][1]) is not None:
        # only collect TEL forms when N is phone-like at all, so files whose
        # N holds a real name pay nothing
        remove_n = is_n_redundant_with_tel(fields["N"][1], tel_phone_forms(lines))
    n_val = fields["N"][1]
    if not remove_n and n_val and "@" in n_val:
        # gate on a plain '@': an e-mail that a name parser split into N's
        # sub-fields no longer matches EMAIL_RE, but still contains one
        email_values = email_value_forms(lines)
        cleaned = strip_redundant_emails(n_val, email_values)
        if cleaned is not None:
            if not any(c.isalnum() for c in cleaned):
                remove_n = True
            else:
                n_new_val = cleaned
        elif is_n_only_split_email(n_val, email_token_forms(lines)):
            remove_n = True

    new_lines = apply_changes(lines, fields, replace_fn, remove_n, strip_inv,
                              n_new_val, blank_n)

    if dedup:
        new_lines = dedup_lines(new_lines)

    folded = [physical for line in new_lines for physical in fold_line(line)]
    return "\n".join(folded)

PROPERTY_NAME_RE = re.compile(r'[A-Za-z][A-Za-z0-9-]*(\.[A-Za-z][A-Za-z0-9-]*)*')
CONTROL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
VALID_ESCAPES = 'nN,;:\\'

VALIDATION_BOOTSTRAP = """Error: --validate needs a third-party parsing library that this
interpreter cannot import. The script itself stays standard-library only; the
checker lives in a uv-managed venv instead:

    uv venv .venv --python 3.14
    uv pip install --python .venv vobject
    .venv/bin/python vcf-cleaner.py IN OUT --validate

or run it in one go:

    uv run --with vobject vcf-cleaner.py IN OUT --validate
"""

def validate_vcard(text, validate_ical=False):
    """Returns a list of human-readable reasons why a written vCard is invalid.

    An empty list means nothing found a problem. The checks that need no
    third-party library always run: physical lines stay within MAX_LINE_BYTES,
    line endings are CRLF pairs, BEGIN/END markers are paired, and every
    content line is a 'NAME[;params]:value' property (or a continuation) with a
    VCard-legal name, printable characters and only legal escape sequences.
    When vobject is importable it is asked as a second tier, which adds value
    level checks such as an unterminated parameter quote. validate_ical
    additionally asks icalendar, which is stricter than VCard 3.0 (it insists
    that N and ADR carry their full subfield counts and that a file hold a
    single card), so it can flag cards that VCard 3.0 readers accept; it is an
    opt-in extra tier, not the gate.
    """
    problems = []

    if '\r' in text.replace('\r\n', '') or '\n' in text.replace('\r\n', ''):
        problems.append("line endings are not plain CRLF pairs")
    physical = text.split('\r\n')
    stack = []
    fn_count = 0
    seen_property = False
    for i, line in enumerate(physical):
        size = len(line.encode('utf-8'))
        if size > MAX_LINE_BYTES:
            problems.append(f"physical line {i + 1} is {size} bytes "
                            f"(over {MAX_LINE_BYTES})")
            continue
        if not line:
            continue
        if line[:1] in (' ', '\t'):
            if not seen_property:
                problems.append(f"physical line {i + 1} continues a line that "
                                f"does not exist")
            continue
        seen_property = True
        if ':' not in line:
            problems.append(f"physical line {i + 1} is not a property line "
                            f"(no ':')")
            continue
        head = line.split(':', 1)[0]
        name = head.split(';', 1)[0]
        if PROPERTY_NAME_RE.fullmatch(name) is None:
            problems.append(f"physical line {i + 1} has no VCard-legal property "
                            f"name")
            continue
        if CONTROL_RE.search(line):
            problems.append(f"physical line {i + 1} holds a control character")
        if head.count('"') % 2:
            problems.append(f"physical line {i + 1} opens a parameter quote "
                            f"that it never closes")
        for m in re.finditer(r'\\.', line):
            if m.group()[1] not in VALID_ESCAPES:
                problems.append(f"physical line {i + 1} escapes an unsupported "
                                f"character")
                break
        prop = get_property(line)
        if prop == 'BEGIN':
            stack.append(line.split(':', 1)[1].strip().upper())
        elif prop == 'END':
            want = line.split(':', 1)[1].strip().upper()
            if not stack or stack[-1] != want:
                problems.append(f"physical line {i + 1} ends a group that was "
                                f"never opened")
            else:
                stack.pop()
        elif prop == 'FN':
            fn_count += 1
    if stack:
        problems.append("a BEGIN: marker is never matched by its END: marker")
    if fn_count > 1:
        problems.append(f"FN appears {fn_count} times in one card")

    # vobject tier: importable only when the checker was installed (see
    # VALIDATION_BOOTSTRAP); a missing library is reported up front by main()
    try:
        import vobject
    except ImportError:
        pass
    else:
        try:
            vobject.readOne(text)
        except Exception as e:
            problems.append(f"vobject rejects it: {type(e).__name__}: {e}")

    if validate_ical:
        try:
            import icalendar
        except ImportError:
            pass
        else:
            try:
                icalendar.Calendar.from_ical(text.encode('utf-8'))
            except Exception as e:
                problems.append(f"icalendar rejects it: {type(e).__name__}: {e}")

    return problems

def process_one(filename, source_path, dest_path, dry_run, strip_inv, dedup,
                validate=False, validate_ical=False, blank_n=False):
    """Reads one .vcf file, transforms it and (unless dry_run) writes it out.
    With validate it also checks the resulting vCard (see validate_vcard).
    Returns (changed, report_lines, failed, invalid)."""
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            content = f.read()

        transformed_content = transform_vcard_content(content, strip_inv=strip_inv,
                                                      dedup=dedup, blank_n=blank_n)

        if transformed_content == content:
            return False, [], False, False

        invalid_report = []
        if validate:
            # what lands on disk is the CRLF form of the transform output
            problems = validate_vcard(transformed_content.replace('\n', '\r\n'),
                                      validate_ical)
            if problems:
                invalid_report = [f"[INVALID OUTPUT] {filename}"]
                invalid_report += [f"         {p}" for p in problems]
                if dry_run:
                    return True, invalid_report, False, True
                # a real run still writes the file: the change was asked for,
                # and silently dropping it would hide the problem

        if dry_run:
            old_fn = extract_fn_value(content)
            new_fn = extract_fn_value(transformed_content)
            fn_changed = (old_fn != new_fn)

            content_lines = unfold_lines(content.split('\n'))
            transformed_lines = unfold_lines(transformed_content.split('\n'))

            def get_rest(lines): return [l for l in lines if get_property(l) != "FN"]
            dedup_happened = (get_rest(content_lines) != get_rest(transformed_lines))

            report = [f"[CHANGE] {filename}"]
            if fn_changed:
                report.append(f"         FN: '{old_fn}'  -->  '{new_fn}'")
            if dedup_happened:
                report.append("         [Deduplication applied]")
            if not fn_changed and not dedup_happened:
                report.append("         [Line re-wrapping applied]")
            return True, report, False, False

        with open(dest_path, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(transformed_content)
        return True, invalid_report, False, bool(invalid_report)

    except Exception as e:
        return False, [f"Error with file {filename}: {e}"], True, False

def batch_process_vcards(source_folder, destination_folder, dry_run=True, strip_inv=True, dedup=True, workers=None, validate=False, validate_ical=False, blank_n=False):
    """Process a folder and return (ok, invalid_outputs).

    ok is False if setup or any file processing fails; invalid_outputs counts
    the written (or, in a dry run, the would-be written) vCards that
    validate_vcard found problems with.
    """
    if dry_run:
        print("="*60)
        print("!!! DRY RUN MODE ACTIVE: NO files will be written !!!")
        print("="*60 + "\n")

    try:
        filenames = sorted([f for f in os.listdir(source_folder) if f.lower().endswith(".vcf")])
    except OSError as e:
        print(f"Error: Cannot read input directory '{source_folder}': {e}")
        return False, 0

    if not filenames:
        print(f"No .vcf files found in '{source_folder}'.")
        return True, 0

    if not dry_run:
        destination_existed = os.path.exists(destination_folder)
        try:
            os.makedirs(destination_folder, exist_ok=True)
        except OSError as e:
            print(f"Error: Cannot create output directory '{destination_folder}': {e}")
            return False, 0
        if not destination_existed:
            print(f"Directory '{destination_folder}' has been created.")

    count_total = len(filenames)
    count_transformed = 0
    count_failed = 0
    count_invalid = 0
    tasks = [(filename,
              os.path.join(source_folder, filename),
              os.path.join(destination_folder, filename))
             for filename in filenames]

    if workers is None:
        workers = 1  # files are tiny and CPU-bound; threading only pays off
                     # for large workloads, so it stays opt-in

    if workers and workers > 1 and count_total > 1:
        # Per-file tasks are tiny and the transform is CPU-bound, so per-task
        # threading mostly pays scheduling overhead. Tasks are grouped into
        # batches (keeps the report order deterministic) so threading only
        # pays off when files are large or numerous enough to be worth it.
        chunk = max(1, count_total // (workers * 4))
        batches = [tasks[i:i + chunk] for i in range(0, count_total, chunk)]
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = [r for batch in executor.map(
                lambda batch: [process_one(*t, dry_run, strip_inv, dedup,
                                           validate, validate_ical, blank_n)
                               for t in batch], batches) for r in batch]
    else:
        results = [process_one(t[0], t[1], t[2], dry_run, strip_inv, dedup,
                                validate, validate_ical, blank_n) for t in tasks]

    for changed, report, failed, invalid in results:
        for line in report:
            print(line)
        if changed:
            count_transformed += 1
        if failed:
            count_failed += 1
        if invalid:
            count_invalid += 1

    print("\n" + "="*60)
    if dry_run:
        print("DRY RUN RESULTS:")
        print(f"Found .vcf files:          {count_total}")
        print(f"Files that would be changed: {count_transformed}")
        print(f"Files that failed:          {count_failed}")
        if validate:
            print(f"Files with invalid output:  {count_invalid}")
    else:
        print("PROCESSING COMPLETE:")
        print(f"Total files processed:       {count_total}")
        print(f"Files saved in destination:   {count_transformed}")
        print(f"Files that failed:            {count_failed}")
        if validate:
            print(f"Files with invalid output:    {count_invalid}")
        if count_transformed > 0:
            print(f"Results are located in:     {os.path.abspath(destination_folder)}")
        else:
            print("Note: No files needed to be changed.")
    print("="*60)
    return count_failed == 0, count_invalid

def main():
    parser = argparse.ArgumentParser(description="vCard clean & fix: Replaces FN with ORG if FN is content that appears redundantly in other fields.")
    parser.add_argument("input", help="Source directory")
    parser.add_argument("output", help="Destination directory")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Simulates the process")
    parser.add_argument("--strip-invisible", action=argparse.BooleanOptionalAction, default=True,
                        help="Remove zero-width/invisible characters (e.g. U+200B) that render like extra spaces (default: on)")
    parser.add_argument("--dedup", action=argparse.BooleanOptionalAction, default=True,
                        help="Remove duplicate lines (default: on)")
    parser.add_argument("--workers", type=int, default=None,
                        help="Files to process in parallel; 1 disables threading "
                             "(default: 1; try e.g. 2-4x CPU count for large inputs)")
    parser.add_argument("--validate", action=argparse.BooleanOptionalAction, default=False,
                        help="Check the resulting vCards and report the invalid ones "
                             "(default: off; the structural rules need no dependency, "
                             "vobject adds value-level checks -- if it is missing the "
                             "command fails and prints how to install it, see README)")
    parser.add_argument("--validate-ical", action=argparse.BooleanOptionalAction, default=False,
                        help="Additionally ask icalendar when validating; it is stricter "
                             "than VCard 3.0 and can flag cards a 3.0 reader accepts "
                             "(default: off)")
    parser.add_argument("--blank-n", action=argparse.BooleanOptionalAction, default=False,
                        help="When a fully redundant N line would be dropped, keep it "
                             "as the empty 'N:;;;;' instead of removing it: VCard 3.0 "
                             "(RFC 2426) mandates the N property and its ABNF allows "
                             "all five sub-fields to be empty (default: off)")
    args = parser.parse_args()
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be at least 1")
    if args.validate_ical and not args.validate:
        parser.error("--validate-ical only makes sense together with --validate")

    if args.validate:
        # the checker libraries are optional: the script is standard-library only
        # and degrades to its own structural rules when they are missing, but an
        # explicitly requested --validate without them would silently under-report
        needed = ["vobject"] + (["icalendar"] if args.validate_ical else [])
        missing = [name for name in needed if importlib.util.find_spec(name) is None]
        if missing:
            print(VALIDATION_BOOTSTRAP)
            print(f"Missing: {', '.join(missing)}")
            raise SystemExit(1)

    success, invalid_outputs = batch_process_vcards(
        args.input, args.output, dry_run=args.dry_run,
        strip_inv=args.strip_invisible, dedup=args.dedup,
        workers=args.workers, validate=args.validate,
        validate_ical=args.validate_ical, blank_n=args.blank_n)
    if not success:
        raise SystemExit(1)
    if invalid_outputs:
        # a distinct status lets a caller tell "the run broke" from "the output
        # vCards are not valid VCards"
        raise SystemExit(2)

if __name__ == "__main__":
    main()
