import csv
import sys

def merge_kd_methods(dataset_path, manual_path, output_path):
    # Read manual Kd methods
    manual_methods = {}
    with open(manual_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdb_id = row.get('pdb', '').lower()
            kd_method = row.get('kd_method', '').strip()
            if pdb_id and kd_method:
                manual_methods[pdb_id] = kd_method
    
    print(f"Found {len(manual_methods)} manual Kd method entries")
    
    # Read dataset and update kd_method
    updated_rows = []
    updated_count = 0
    with open(dataset_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            pdb_id = row.get('pdb', '').lower()
            current_method = row.get('kd_method', '').strip()
            
            # Update if manual method exists and current is Unknown or empty
            if pdb_id in manual_methods and (current_method == 'Unknown' or current_method == '' or current_method == ''):
                row['kd_method'] = manual_methods[pdb_id]
                updated_count += 1
            
            updated_rows.append(row)
    
    print(f"Updated {updated_count} entries with manual Kd methods")
    
    # Write updated dataset
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    print(f"Successfully updated dataset saved to {output_path}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python merge_kd_methods.py <dataset_path> <manual_path> <output_path>")
        sys.exit(1)
    dataset_path = sys.argv[1]
    manual_path = sys.argv[2]
    output_path = sys.argv[3]
    merge_kd_methods(dataset_path, manual_path, output_path)
