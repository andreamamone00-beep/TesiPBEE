"""Script per aggiornare dataset2 con dati di affinità dalla letteratura."""
import csv
import math
from pathlib import Path

# Costante gas R in kcal/(mol·K)
R_GAS_KCAL = 1.987204e-3
TEMPERATURE = 298.15  # K

def kd_to_dg(kd_nm: float) -> float:
    """Converte Kd in nM a ΔG in kcal/mol."""
    kd_molar = kd_nm * 1e-9  # Converti nM → M
    dg = R_GAS_KCAL * TEMPERATURE * math.log(kd_molar)
    return dg

def main():
    data_dir = Path(__file__).parent.parent / "data"
    dataset2_path = data_dir / "dataset2.csv"
    affinity_path = data_dir / "dataset2_affinity_data.csv"
    
    # Leggi dati di affinità
    affinity_data = {}
    with affinity_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdb_id = row["pdb"].lower()
            affinity_data[pdb_id] = {
                "kd_nM": float(row["kd_nM"]),
                "method": row["method"],
                "source": row["source"],
                "reference": row["reference"]
            }
    
    print(f"Caricati {len(affinity_data)} dati di affinità")
    
    # Leggi dataset2
    with dataset2_path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    # Aggiorna record con dati di affinità
    updated_rows = []
    for row in rows:
        pdb_id = row.get("pdb", "").lower()
        
        if pdb_id in affinity_data:
            aff = affinity_data[pdb_id]
            row["kd_nM"] = aff["kd_nM"]
            row["method"] = aff["method"]
            row["source"] = aff["source"]
            
            # Calcola dG_exp
            dg_exp = kd_to_dg(aff["kd_nM"])
            row["dG_exp_kcal_mol"] = round(dg_exp, 3)
            
            # Calcola delta
            if row.get("dG_pred_kcal_mol"):
                try:
                    dg_pred = float(row["dG_pred_kcal_mol"])
                    delta = dg_pred - dg_exp
                    row["delta_kcal_mol"] = round(delta, 3)
                except (ValueError, TypeError):
                    pass
            
            print(f"{pdb_id}: KD={aff['kd_nM']} nM, dG_exp={dg_exp:.3f} kcal/mol")
        
        updated_rows.append(row)
    
    # Salva dataset aggiornato
    output_path = data_dir / "dataset2_final.csv"
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    print(f"Salvati {len(updated_rows)} record in {output_path}")

if __name__ == "__main__":
    main()
