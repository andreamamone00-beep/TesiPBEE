import csv
import sys

def manual_pbee_entry(dataset_path, output_path):
    # Read dataset
    with open(dataset_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Find rows with missing PBEE values
    missing_rows = []
    for i, row in enumerate(rows):
        if not row.get('dG_pred_kcal_mol', '').strip():
            missing_rows.append((i, row))

    print(f"Found {len(missing_rows)} entries with missing PBEE values")
    print("=" * 80)

    # Ask user for values
    for idx, row in missing_rows:
        pdb_id = row['pdb']
        kd_nM = row.get('kd_nM', 'N/A')
        antigen = row.get('antigen', 'N/A')[:50]  # Truncate long antigen names

        print(f"\nPDB: {pdb_id} | Kd: {kd_nM} nM | Antigen: {antigen}...")
        print("Enter PBEE values (leave blank to skip):")

        dG_pred = input(f"  dG_pred_kcal_mol: ").strip()
        if dG_pred:
            row['dG_pred_kcal_mol'] = dG_pred
            row['dG_pred_electrostatic'] = input(f"  dG_pred_electrostatic: ").strip()
            row['dG_pred_apolar'] = input(f"  dG_pred_apolar: ").strip()
            row['dG_pred_entropy'] = input(f"  dG_pred_entropy: ").strip()

            # Calculate delta if all values are provided
            try:
                dG_exp = float(row.get('dG_exp_kcal_mol', 0))
                dG_pred_val = float(dG_pred)
                delta = dG_exp - dG_pred_val
                row['delta_kcal_mol'] = str(round(delta, 3))
                print(f"  Calculated delta: {row['delta_kcal_mol']}")
            except ValueError:
                row['delta_kcal_mol'] = ''
        else:
            print("  Skipped")

    # Write updated dataset
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("\n" + "=" * 80)
    print(f"Successfully updated dataset saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python manual_pbee_entry.py <dataset_path> <output_path>")
        print("Example: python manual_pbee_entry.py data/dataset.csv data/dataset.csv")
        sys.exit(1)
    dataset_path = sys.argv[1]
    output_path = sys.argv[2]
    manual_pbee_entry(dataset_path, output_path)
