from pathlib import Path
import csv
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

from sources import load_sabdab_summary, parse_affinity_string


def test_load_sabdab_summary_parses_supplied_rows(tmp_path):
    tsv = tmp_path / 'sabdab.tsv'
    tsv.write_text(
        'pdb\tHchain\tLchain\tmethod\tresolution\taffinity\tantigen_name\theavy_species\tlight_species\n'
        '4jn2\tH\tL\tX-RAY DIFFRACTION\t1.71\t0.00\t3-({2-[(4-CARBAMIMIDOYL-PHENYLAMINO)-METHYL]-3-METHYL-3H-BENZOIMIDAZOLE-5-CARBONYL}-PYRIDIN-2-YL-AMINO)-PROPIONIC ACID ETHYL ESTER\thomo sapiens\thomo sapiens\n',
        encoding='utf-8',
    )

    rows = load_sabdab_summary(tsv)
    assert len(rows) == 1
    assert rows[0]['pdb'] == '4jn2'
    assert rows[0]['affinity'] == '0.00'
    assert rows[0]['antigen_name'] == '3-({2-[(4-CARBAMIMIDOYL-PHENYLAMINO)-METHYL]-3-METHYL-3H-BENZOIMIDAZOLE-5-CARBONYL}-PYRIDIN-2-YL-AMINO)-PROPIONIC ACID ETHYL ESTER'


def test_parse_affinity_string_supports_plain_decimal_um_values():
    assert parse_affinity_string('0.01') == 10.0
    assert parse_affinity_string('5.0') == 5000.0
