import csv
import sys

def clear_pbee_values(dataset_path, output_path):
    # Read dataset and clear PBEE values
    updated_rows = []
    with open(dataset_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            # Clear PBEE calculated columns
            pbee_columns = ['dG_pred_kcal_mol', 'dG_pred_electrostatic', 'dG_pred_apolar', 'dG_pred_entropy', 'delta_kcal_mol']
            for col in pbee_columns:
                if col in row:
                    row[col] = ''
            updated_rows.append(row)

    # Write updated dataset
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"Successfully cleared PBEE values from {dataset_path} and saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python clear_pbee_values.py <dataset_path> <output_path>")
        sys.exit(1)
    dataset_path = sys.argv[1]
    output_path = sys.argv[2]
    clear_pbee_values(dataset_path, output_path)
