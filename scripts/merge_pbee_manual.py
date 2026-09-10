import csv
import sys

def merge_pbee_manual(dataset_path, template_path, output_path):
    # Read manual PBEE values from template
    manual_values = {}
    error_values = {}
    with open(template_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdb_id = row.get('pdb', '').lower()
            values = {
                'dG_pred_kcal_mol': (row.get('dG_pred_kcal_mol') or '').strip(),
                'dG_pred_electrostatic': (row.get('dG_pred_electrostatic') or '').strip(),
                'dG_pred_apolar': (row.get('dG_pred_apolar') or '').strip(),
                'dG_pred_entropy': (row.get('dG_pred_entropy') or '').strip()
            }
            # Check if marked as error
            if pdb_id and values['dG_pred_kcal_mol'].lower() in ['errore', 'error']:
                error_values[pdb_id] = 'N/A'
            # Only add if dG_pred_kcal_mol has a numeric value
            elif pdb_id and values['dG_pred_kcal_mol'] and values['dG_pred_kcal_mol'].lower() not in ['', 'n/a', 'none']:
                manual_values[pdb_id] = values

    print(f"Found {len(manual_values)} entries with manual PBEE values")
    print(f"Found {len(error_values)} entries marked as error")
    print(f"Manual PDB IDs: {list(manual_values.keys())[:5]}...")
    print(f"Error PDB IDs: {list(error_values.keys())[:5]}...")

    # Read dataset and update with manual values
    updated_rows = []
    updated_count = 0
    error_count = 0
    with open(dataset_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        # Add delta_kcal_mol if not present
        if 'delta_kcal_mol' not in fieldnames:
            fieldnames.append('delta_kcal_mol')
        for row in reader:
            pdb_id = row.get('pdb', '').strip().lower()

            if pdb_id in manual_values:
                values = manual_values[pdb_id]
                row['dG_pred_kcal_mol'] = values['dG_pred_kcal_mol']
                row['dG_pred_electrostatic'] = values['dG_pred_electrostatic']
                row['dG_pred_apolar'] = values['dG_pred_apolar']
                row['dG_pred_entropy'] = values['dG_pred_entropy']

                # Calculate delta if dG_pred is provided
                if values['dG_pred_kcal_mol']:
                    try:
                        dG_exp = float(row.get('dG_exp_kcal_mol', 0))
                        dG_pred_val = float(values['dG_pred_kcal_mol'])
                        delta = dG_exp - dG_pred_val
                        row['delta_kcal_mol'] = str(round(delta, 3))
                    except ValueError:
                        row['delta_kcal_mol'] = ''
                else:
                    row['delta_kcal_mol'] = ''

                updated_count += 1
                print(f"Updated: {pdb_id} with dG_pred={values['dG_pred_kcal_mol']}")
            elif pdb_id in error_values:
                # Mark as N/A for PBEE calculation failure
                row['dG_pred_kcal_mol'] = 'N/A'
                row['dG_pred_electrostatic'] = 'N/A'
                row['dG_pred_apolar'] = 'N/A'
                row['dG_pred_entropy'] = 'N/A'
                row['delta_kcal_mol'] = 'N/A'
                error_count += 1
                print(f"Marked as error: {pdb_id}")

            updated_rows.append(row)

    print(f"Updated {updated_count} entries")

    # Write updated dataset
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"Successfully merged manual PBEE values to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python merge_pbee_manual.py <dataset_path> <template_path> <output_path>")
        print("Example: python merge_pbee_manual.py data/dataset.csv data/dataset_pbee_template.csv data/dataset.csv")
        sys.exit(1)
    dataset_path = sys.argv[1]
    template_path = sys.argv[2]
    output_path = sys.argv[3]
    merge_pbee_manual(dataset_path, template_path, output_path)
