import re
import os
import argparse
from concurrent.futures import ThreadPoolExecutor

MAX_LINE_BYTES = 75
INVISIBLE_RE = re.compile(r'[\u200b\u200c\u200d\u2060\ufeff]')
EMAIL_RE = re.compile(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}')
NONPHONE_RE = re.compile(r'[^\d+]')
PHONE_RE = re.compile(r'^\+?\d+$')
NONSEP_RE = re.compile(r'[^a-zA-Z0-9]')
WS_RE = re.compile(r'\s+')

def normalize_phone(text):
    """
    Extracts only digits and the plus sign from a string.
    Example: '+34 933-173 022' -> '+34933173022'
    """
    if not text:
        return ""
    return NONPHONE_RE.sub('', text)

def normalize_content(text):
    """
    Removes all non-alphanumeric characters, lowercases the text, and sorts the characters.
    Used for general redundancy checks (e.g., addresses) where order might differ.
    """
    if not text:
        return ""
    return "".join(sorted(NONSEP_RE.sub('', text).lower()))

def get_property(line):
    """Returns the property name of a VCard line (text before ';' or ':'), or None.
    Example: 'ORG;CHARSET=UTF-8:Foo' -> 'ORG'
    """
    if ":" not in line:
        return None
    return line.split(":", 1)[0].split(";", 1)[0]

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
    - contents: set of normalize_content(value) of every line with a ':'
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
    return n_norm != "" and n_norm == normalize_content(adr_val)

def extract_fn_value(vcard_text):
    """Returns the FN value of a vCard (unfolded), for dry-run display."""
    for line in unfold_lines(vcard_text.splitlines()):
        if get_property(line) == "FN":
            return line.split(":", 1)[1].strip()
    return "Unknown"

def apply_changes(lines, fields, replace_fn, remove_n, strip_inv):
    """Returns the lines with FN replaced by ORG and/or N removed.
    A kept FN line's value is whitespace-normalized (its property prefix is kept)."""
    fn_idx = fields["FN"][0]
    n_idx = fields["N"][0]
    new_lines = []
    for i, line in enumerate(lines):
        if i == n_idx and remove_n:
            continue
        if i == fn_idx:
            if replace_fn:
                org_val = fields["ORG"][1]
                new_lines.append(f"FN:{collapse_spaces(org_val, strip_inv=strip_inv)}")
            else:
                prop_part = line.split(":", 1)[0]
                fn_value = collapse_spaces(line.split(":", 1)[1], strip_inv=strip_inv) if ":" in line else ""
                new_lines.append(f"{prop_part}:{fn_value}")
        else:
            new_lines.append(line)
    return new_lines

def transform_vcard_content(vcard_text, strip_inv=True, dedup=True):
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

    Deduplication logic:
    Perform line-level deduplication (enabled by the dedup flag).

    The strip_inv flag enables removal of zero-width/invisible characters;
    the dedup flag enables line-level deduplication.
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

    new_lines = apply_changes(lines, fields, replace_fn, remove_n, strip_inv)

    if dedup:
        new_lines = dedup_lines(new_lines)

    folded = [physical for line in new_lines for physical in fold_line(line)]
    return "\n".join(folded)

def process_one(filename, source_path, dest_path, dry_run, strip_inv, dedup):
    """Reads one .vcf file, transforms it and (unless dry_run) writes it out.
    Returns (changed, report_lines) where report_lines describe the change."""
    try:
        with open(source_path, 'r', encoding='utf-8') as f:
            content = f.read()

        transformed_content = transform_vcard_content(content, strip_inv=strip_inv, dedup=dedup)

        if transformed_content == content:
            return False, []

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
            return True, report

        with open(dest_path, 'w', encoding='utf-8', newline='\r\n') as f:
            f.write(transformed_content)
        return True, []

    except Exception as e:
        return False, [f"Error with file {filename}: {e}"]

def batch_process_vcards(source_folder, destination_folder, dry_run=True, strip_inv=True, dedup=True, workers=None):
    if dry_run:
        print("="*60)
        print("!!! DRY RUN MODE ACTIVE: NO files will be written !!!")
        print("="*60 + "\n")
    else:
        if not os.path.exists(destination_folder):
            os.makedirs(destination_folder)
            print(f"Directory '{destination_folder}' has been created.")

    count_total = 0
    count_transformed = 0

    try:
        filenames = sorted([f for f in os.listdir(source_folder) if f.lower().endswith(".vcf")])
    except FileNotFoundError:
        print(f"Error: The directory '{source_folder}' does not exist.")
        return

    if not filenames:
        print(f"No .vcf files found in '{source_folder}'.")
        return

    count_total = len(filenames)
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
                lambda batch: [process_one(*t, dry_run, strip_inv, dedup)
                               for t in batch], batches) for r in batch]
    else:
        results = [process_one(t[0], t[1], t[2], dry_run, strip_inv, dedup) for t in tasks]

    for changed, report in results:
        for line in report:
            print(line)
        if changed:
            count_transformed += 1

    print("\n" + "="*60)
    if dry_run:
        print("DRY RUN RESULTS:")
        print(f"Found .vcf files:          {count_total}")
        print(f"Files that would be changed: {count_transformed}")
    else:
        print("PROCESSING COMPLETE:")
        print(f"Total files processed:       {count_total}")
        print(f"Files saved in destination:   {count_transformed}")
        if count_transformed > 0:
            print(f"Results are located in:     {os.path.abspath(destination_folder)}")
        else:
            print("Note: No files needed to be changed.")
    print("="*60)

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
    args = parser.parse_args()
    if args.workers is not None and args.workers < 1:
        parser.error("--workers must be at least 1")
    batch_process_vcards(args.input, args.output, dry_run=args.dry_run,
                         strip_inv=args.strip_invisible, dedup=args.dedup,
                         workers=args.workers)

if __name__ == "__main__":
    main()
