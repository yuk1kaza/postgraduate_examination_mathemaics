"""Check source fingerprints, question IDs and page references; not exam difficulty."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check(evidence, examples):
    manifest = load(evidence / "source-manifest.json")
    sources = {row["file"]: row for row in manifest["files"]}
    errors = []
    for name, row in sources.items():
        pdf = examples / name
        if not pdf.is_file():
            errors.append(f"Missing PDF: {pdf}")
        elif hashlib.sha256(pdf.read_bytes()).hexdigest() != row["sha256"]:
            errors.append(f"Source changed; recheck its index: {pdf}")

    historical = load(evidence / "historical-question-index.json")
    recent = load(evidence / "recent-question-index.json")
    rows = historical + recent
    ids = Counter((row["year"], row["question"]) for row in rows)
    expected = {(y, n) for y in range(2010, 2027)
                for n in range(1, 24 if y <= 2020 else 23)}
    for key in expected - ids.keys():
        errors.append(f"Missing question: {key}")
    for key in ids.keys() - expected:
        errors.append(f"Unexpected question: {key}")
    for key, count in ids.items():
        if count != 1:
            errors.append(f"Duplicate question: {key} ({count})")

    for row in rows:
        source = row.get("source_file") or row.get("source", "")
        name = re.split(r"[/\\]", source)[-1]
        if name not in sources:
            errors.append(f"Unknown source: {source}")
            continue
        page_field = row.get("pdf_physical_pages", row.get("physical_page"))
        pages = [int(p) for p in re.findall(r"\d+", str(page_field))]
        if not pages or any(not 1 <= p <= sources[name]["pages"] for p in pages):
            errors.append(f"Invalid pages: {row['year']}-{row['question']}: {page_field}")

    summaries = []
    for year in range(2021, 2027):
        paper = [r for r in recent if r["year"] == year]
        if sum(r["points"] for r in paper) != 150:
            errors.append(f"Points do not sum to 150: {year}")
        composition = Counter(r["kind"] for r in paper)
        if sorted(composition.values()) != [6, 6, 10]:
            errors.append(f"Unexpected section sizes: {year}: {composition}")
        subjects = Counter()
        for r in paper:
            subjects[r["subject"]] += r["points"]
        summaries.append({"year": year, "questions": len(paper),
                          "subject_points": dict(subjects)})
    return {"passed": not errors, "questions": len(rows),
            "source_pdfs": len(sources), "recent_papers": summaries,
            "errors": errors,
            "scope": "Identity, coverage, fingerprints and allocation only; not proof of mathematics or difficulty."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--examples", type=Path, required=True)
    parser.add_argument("--evidence", type=Path,
                        default=Path(__file__).resolve().parents[1] / "references" / "evidence")
    args = parser.parse_args()
    result = check(args.evidence, args.examples)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
