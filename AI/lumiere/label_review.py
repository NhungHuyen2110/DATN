"""Convert explicitly approved review rows into a NEW validated public CSV.

No graph or database writes occur here. Human review is recorded as a source;
candidate confidence is never treated as approval.
"""
import csv
import hashlib
from pathlib import Path

from .catalog import CsvProductRepository, TAXONOMY
from .configuration import load_aliases


def export_reviewed_labels(source: Path, review: Path, destination: Path):
    if destination.exists() or destination.resolve() in {source.resolve(), review.resolve()}:
        raise ValueError("Destination must be a new file, different from inputs")
    CsvProductRepository(source).all()
    source_hash, review_hash = (hashlib.sha256(p.read_bytes()).hexdigest() for p in (source, review))
    with source.open(encoding="utf-8-sig", newline="") as f:
        records = list(csv.DictReader(f))
    with review.open(encoding="utf-8-sig", newline="") as f:
        reviews = list(csv.DictReader(f))
    public_fields = ["ProductID","SKU","ProductName","SalePrice","Stock", *[kind+suffix for kind in TAXONOMY for suffix in ("ID","Name")]]
    optional = [kind+suffix for kind in ("Audience","Style","Occasion") for suffix in ("ID","Name","Evidence")]
    fields = [*public_fields, "Published", *optional]
    output = {int(row["ProductID"]): {key:row.get(key, "true" if key == "Published" else "") for key in fields} for row in records}
    source_records = {int(row["ProductID"]): row for row in records}
    facts, seen = 0, set()
    definitions = load_aliases()["entities"]
    for row in reviews:
        if row.get("review_status") != "APPROVED":
            continue
        reviewer = row.get("reviewer", "").strip()
        ident = int(row["product_id"])
        if not reviewer or ident not in output or ident in seen:
            raise ValueError("Approved row requires reviewer and unique existing product ID")
        seen.add(ident)
        if row.get("source_sha256") != source_hash or row.get("sku") != output[ident]["SKU"]:
            raise ValueError("Review source hash/SKU differs from current catalog")
        for kind, column in (("audience","Audience"), ("style","Style"), ("occasion","Occasion")):
            canonical = row.get("candidate_"+kind, "").strip()
            if not canonical:
                continue
            evidence, field = row.get(kind+"_evidence", "").strip(), row.get(kind+"_evidence_field", "").strip()
            confidence = float(row.get(kind+"_confidence", ""))
            if canonical not in definitions[kind] or not evidence or not 0 <= confidence <= 1:
                raise ValueError("Approved label needs canonical ID, evidence and confidence in 0..1")
            if field == "human_review":
                if not row.get("review_notes", "").strip():
                    raise ValueError("Human annotation requires an explicit review note")
            elif not field or evidence not in source_records[ident].get(field, ""):
                raise ValueError("Evidence span is absent from the identified source field")
            output[ident].update({column+"ID":canonical, column+"Name":definitions[kind][canonical]["name"],
                column+"Evidence": f"{evidence} | field={field}; reviewer={reviewer}; confidence={confidence}; review_sha256={review_hash}; source_sha256={source_hash}; status=APPROVED"})
            facts += 1
    if not facts:
        return {"status":"PENDING_REVIEW", "exported_facts":0, "exported":False}
    # Validate before making the destination visible.
    import tempfile
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", newline="", suffix=".csv", dir=destination.parent, delete=False) as temporary:
        staged = Path(temporary.name)
        writer = csv.DictWriter(temporary, fields)
        writer.writeheader()
        writer.writerows(output.values())
    try:
        CsvProductRepository(staged).all()
        if destination.exists():
            raise ValueError("Destination appeared during export; refusing overwrite")
        staged.rename(destination)
    finally:
        # Only the exact temporary file created above can be removed.
        if staged.exists():
            staged.unlink()
    return {"status":"EXPORTED_APPROVED_ONLY", "exported_facts":facts, "exported":True, "review_sha256":review_hash}
