from pathlib import Path
import csv
import importlib.util
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))

build_dataset_spec = importlib.util.spec_from_file_location(
    'build_dataset', Path(__file__).resolve().parents[1] / 'scripts' / '01_build_dataset.py'
)
build_dataset = importlib.util.module_from_spec(build_dataset_spec)
build_dataset_spec.loader.exec_module(build_dataset)
build_from_sabdab = build_dataset.build_from_sabdab
from sources import load_sabdab_summary, parse_affinity_string


def test_load_sabdab_summary_parses_supplied_rows(tmp_path):
    tsv = tmp_path / 'sabdab.tsv'
    tsv.write_text(
        'pdb\tHchain\tLchain\tmethod\tresolution\taffinity\tantigen_name\theavy_species\tlight_species\taffinity_method\n'
        '4jn2\tH\tL\tX-RAY DIFFRACTION\t1.71\t0.00\t3-({2-[(4-CARBAMIMIDOYL-PHENYLAMINO)-METHYL]-3-METHYL-3H-BENZOIMIDAZOLE-5-CARBONYL}-PYRIDIN-2-YL-AMINO)-PROPIONIC ACID ETHYL ESTER\thomo sapiens\thomo sapiens\tBLI\n',
        encoding='utf-8',
    )

    rows = load_sabdab_summary(tsv)
    assert len(rows) == 1
    assert rows[0]['pdb'] == '4jn2'
    assert rows[0]['affinity'] == '0.00'
    assert rows[0]['affinity_method'] == 'BLI'
    assert rows[0]['antigen_name'] == '3-({2-[(4-CARBAMIMIDOYL-PHENYLAMINO)-METHYL]-3-METHYL-3H-BENZOIMIDAZOLE-5-CARBONYL}-PYRIDIN-2-YL-AMINO)-PROPIONIC ACID ETHYL ESTER'


def test_build_from_sabdab_uses_affinity_method_as_kd_method(tmp_path):
    tsv = tmp_path / 'sabdab.tsv'
    tsv.write_text(
        'pdb\tHchain\tLchain\tmethod\tresolution\taffinity\tantigen_name\theavy_species\tlight_species\taffinity_method\n'
        '1abc\tH\tL\tX-RAY DIFFRACTION\t1.80\t1.0e-09\tTarget\thomo sapiens\thomo sapiens\tSPR\n',
        encoding='utf-8',
    )

    rows = build_from_sabdab(tsv, max_hits=1)
    assert len(rows) == 1
    assert rows[0]['kd_method'] == 'SPR'


def test_parse_affinity_string_supports_decimal_um_values():
    assert parse_affinity_string('Kd = 0.01 uM') == 10.0
    assert parse_affinity_string('5.0e-6') == 5000.0
