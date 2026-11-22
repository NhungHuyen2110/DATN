"""Offline contract tests; generated fixtures are synthetic, not catalog truth."""
import csv
import importlib.util
import json
from pathlib import Path
import tempfile
import unicodedata
import unittest
import builtins
import contextlib
import io
import runpy
import sys
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("csv_validation", ROOT / "AI/knowledge_graph/csv_validation.py")
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class CSVValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.file = self.root / "synthetic.csv"
        self.lookup_dir = self.root / "lookups"
        self.lookup_dir.mkdir()
        self.row = {"ProductID": "1", "SKU": "00001", "Barcode": "000000001", "ProductName": "Nhẫn Phái nữ, mẫu thử",
                    "Weight": "1.25", "SalePrice": "7000000.01", "WholesalePrice": "2", "CostPrice": "1", "Stock": "3"}
        for prefix, (filename, _) in VALIDATOR.LOOKUPS.items():
            name = "Nhẫn" if prefix == "Category" else prefix + " thử nghiệm"
            self.row[prefix + "ID"] = "1"
            self.row[prefix + "Name"] = name
            (self.lookup_dir / (filename + ".json")).write_text(
                json.dumps([{"id": 1, "name": name}], ensure_ascii=False), encoding="utf-8")

    def write(self, rows=None, fields=None, delimiter=","):
        with self.file.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields or list(self.row), delimiter=delimiter)
            writer.writeheader()
            writer.writerows(rows if rows is not None else [self.row])

    def validate(self, **kwargs):
        return VALIDATOR.validate_csv(self.file, self.lookup_dir, **kwargs)

    def test_bom_quoted_vietnamese_nfc_and_exact_money_identity(self):
        self.row["CategoryName"] = unicodedata.normalize("NFD", "Nhẫn")
        self.write()
        result = self.validate()
        self.assertFalse(result["errors"])
        row = result["records"][0]
        self.assertEqual(row["SKU"], "00001")
        self.assertEqual(row["Barcode"], "000000001")
        self.assertEqual(row["CategoryName"], "Nhẫn")
        self.assertEqual(row["ProductName"], "Nhẫn Phái nữ, mẫu thử")
        self.assertEqual(row["SalePrice"], "7000000.01")
        self.assertEqual(row["source_row"], 2)
        self.assertNotIn("Audience", VALIDATOR.summary(result, self.file)["planned_nodes"])

    def test_duplicate_ids_are_reported_and_block_whole_plan(self):
        self.write([self.row, self.row])
        result = self.validate()
        self.assertEqual(result["rows_seen"], 2)
        self.assertTrue(any(e["code"] == "duplicate_identity" for e in result["errors"]))
        self.assertFalse(VALIDATOR.summary(result, self.file)["write_allowed"])

    def test_invalid_numeric_inputs_report_field_and_row(self):
        for field, value in (("ProductID", ""), ("ProductID", "-1"), ("SalePrice", "NaN"),
                             ("SalePrice", "Infinity"), ("SalePrice", "-1"), ("SalePrice", "1.001"),
                             ("Weight", "0"), ("Stock", "-1"), ("Stock", "1.5")):
            with self.subTest(field=field, value=value):
                self.write([dict(self.row, **{field: value})])
                result = self.validate()
                self.assertFalse(result["records"])
                self.assertTrue(any(e["field"] == field and e["row"] == 2 for e in result["errors"]))

    def test_foreign_key_and_lookup_name_drift(self):
        for changes, code in (({"CategoryID": "999"}, "unknown_foreign_key"),
                              ({"CategoryName": "Khác"}, "lookup_name_mismatch")):
            self.write([dict(self.row, **changes)])
            self.assertTrue(any(e["code"] == code for e in self.validate()["errors"]))

    def test_duplicate_header_rejected(self):
        self.file.write_text("ProductID,ProductID\n1,1\n", encoding="utf-8")
        self.assertEqual(self.validate()["errors"][0]["code"], "schema_mismatch")

    def test_missing_field_rejected(self):
        fields = [f for f in self.row if f != "Stock"]
        self.write([{k: v for k, v in self.row.items() if k != "Stock"}], fields=fields)
        self.assertEqual(self.validate()["errors"][0]["code"], "schema_mismatch")

    def test_empty_dataset_rejected(self):
        self.write([])
        self.assertEqual(self.validate()["errors"][0]["code"], "empty_dataset")

    def test_separator_and_explicit_partial_scope(self):
        self.write([self.row, dict(self.row, ProductID="2", SKU="00002", Barcode="000000002")], delimiter=";")
        result = self.validate(delimiter=";", limit=1)
        self.assertEqual(len(result["records"]), 1)
        self.assertEqual(result["scope"], "prefix_only")

    def test_repeated_validation_does_not_change_source(self):
        self.write()
        original = self.file.read_bytes()
        first = VALIDATOR.summary(self.validate(), self.file)
        self.assertEqual(first, VALIDATOR.summary(self.validate(), self.file))
        self.assertEqual(self.file.read_bytes(), original)
        self.assertEqual(first["planned_relationships"]["BELONGS_TO"], 1)

    def test_existing_importer_dispatches_before_env_or_database_imports(self):
        self.write()
        original_import = builtins.__import__

        def offline_import(name, *args, **kwargs):
            if name.split(".")[0] in {"dotenv", "neo4j", "pandas"}:
                raise AssertionError("Dry-run must not load secrets or database/model dependencies")
            return original_import(name, *args, **kwargs)

        argv = ["import_data.py", "--file", str(self.file), "--lookup-dir", str(self.lookup_dir), "--dry-run"]
        with patch.object(sys, "argv", argv), patch.dict(sys.modules, {"csv_validation": VALIDATOR}), \
                patch("builtins.__import__", offline_import), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(ROOT / "AI/knowledge_graph/import_data.py"), run_name="__main__")
        self.assertEqual(result.exception.code, 0)

    def test_apply_without_isolated_target_is_rejected_before_connection(self):
        self.write()
        argv = ['import_data.py', '--file', str(self.file), '--apply']
        with patch.object(sys, 'argv', argv), patch.dict(sys.modules, {'csv_validation': VALIDATOR}), \
                contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(ROOT / 'AI/knowledge_graph/import_data.py'), run_name='__main__')
        self.assertEqual(result.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
