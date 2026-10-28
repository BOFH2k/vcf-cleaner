import re
import os
import argparse

def normalize_phone(text):
    """
    Extracts only digits and the plus sign from a string.
    Example: '+34 933-173 022' -> '+34933173022'
    """
    if not text:
        return ""
    return re.sub(r'[^\d+]', '', text)

def extract_fn_value(vcard_text):
    """Helper function for dry-run display."""
    for line in vcard_text.splitlines():
        if line.startswith("FN:"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                return parts[1].strip()
    return "Unknown"

def transform_vcard_content(vcard_text):
    """
    Transforms a vCard based on redundancy logic:
    1. Is FN a phone number?
    2. If yes: Does this number (normalized) exist exactly as is in another field?
    3. If yes: Replace FN with ORG.
    """
    lines = vcard_text.strip().splitlines()
    
    fn_raw_value = None
    fn_index = -1
    org_raw_value = None

    # 1. Search for FN and ORG
    for i, line in enumerate(lines):
        if line.startswith("FN:"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                fn_raw_value = parts[1].strip()
                fn_index = i
        elif line.startswith("ORG:"):
            parts = line.split(":", 1)
            if len(parts) > 1:
                org_raw_value = parts[1].strip()

    # If no FN found, do nothing
    if fn_raw_value is None:
        return vcard_text

    # 2. Check if FN is a phone number
    fn_normalized = normalize_phone(fn_raw_value)
    is_phone_format = re.match(r'^\+\d+$', fn_normalized) is not None

    if is_phone_format:
        # 3. Redundancy check: Does the number appear in another line?
        is_redundant = False
        for i, line in enumerate(lines):
            if i == fn_index:
                continue  # Skip the FN line itself
            
            # We normalize the entire line to see if the number is in it
            # (This covers TEL, ADR, etc.)
            line_normalized = normalize_phone(line)
            
            # We check for exact match of normalized values
            if line_normalized == fn_normalized and fn_normalized != "":
                is_redundant = True
                break
        
        # 4. Replace only if redundant AND ORG is present
        if is_redundant and org_raw_value:
            new_lines = []
            for i, line in enumerate(lines):
                if i == fn_index:
                    new_lines.append(f"FN:{org_raw_value}")
                else:
                    new_lines.append(line)
            return "\n".join(new_lines)

    return vcard_text

def batch_process_vcards(source_folder, destination_folder, dry_run=True):
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

    for filename in filenames:
        count_total += 1
        source_path = os.path.join(source_folder, filename)
        dest_path = os.path.join(destination_folder, filename)

        try:
            with open(source_path, 'r', encoding='utf-8') as f:
                content = f.read()

            transformed_content = transform_vcard_content(content)

            if transformed_content != content:
                count_transformed += 1
                if dry_run:
                    old_fn = extract_fn_value(content)
                    new_fn = extract_fn_value(transformed_content)
                    print(f"[CHANGE] {filename}")
                    print(f"         FN: '{old_fn}'  -->  '{new_fn}'")
                else:
                    with open(dest_path, 'w', encoding='utf-8') as f:
                        f.write(transformed_content)
            # Unlike the previous version, we do NOT write anything if no change occurs.

        except Exception as e:
            print(f"Error with file {filename}: {e}")

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
    parser = argparse.ArgumentParser(description="VCard Fixer: Replaces FN with ORG if FN is a phone number that appears redundantly in other fields.")
    parser.add_argument("input", help="Source directory")
    parser.add_argument("output", help="Destination directory")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Simulates the process")
    args = parser.parse_args()
    batch_process_vcards(args.input, args.output, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
