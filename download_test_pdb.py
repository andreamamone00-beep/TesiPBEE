"""Script per scaricare alcuni PDB di test per calcoli PBEE."""
import urllib.request
import urllib.error
from pathlib import Path

def download_pdb(pdb_id: str, output_path: Path) -> bool:
    """Scarica un file PDB da RCSB."""
    url = f"https://files.rcsb.org/download/{pdb_id.upper()}.pdb"
    try:
        with urllib.request.urlopen(url, timeout=15) as r, output_path.open("wb") as f:
            f.write(r.read())
        print(f"Scaricato {pdb_id} -> {output_path}")
        return True
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"Errore scaricando {pdb_id}: {e}")
        return False

def main():
    """Scarica alcuni PDB di test dal nostro dataset."""
    structures_dir = Path("data/structures")
    structures_dir.mkdir(exist_ok=True)
    
    # PDB ID dal nostro dataset SAbDab
    test_pdbs = ["5ivn", "2p45", "5imm", "4qyo", "5imk"]
    
    print("Download PDB di test per calcoli PBEE...")
    for pdb_id in test_pdbs:
        output_path = structures_dir / f"{pdb_id.lower()}.pdb"
        if not output_path.exists():
            download_pdb(pdb_id, output_path)
        else:
            print(f"{pdb_id} già esistente")

if __name__ == "__main__":
    main()
