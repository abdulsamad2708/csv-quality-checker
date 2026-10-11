"""Inspect and clean CSV files using only Python's standard library."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path


def make_unique_headers(headers: list[str]) -> list[str]:
    """Normalize header names and make collisions predictable."""
    result: list[str] = []
    used: set[str] = set()
    for index, header in enumerate(headers, start=1):
        base = re.sub(r"[^a-z0-9]+", "_", header.strip().lower()).strip("_")
        base = base or f"column_{index}"
        candidate = base
        suffix = 2
        while candidate in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate)
        result.append(candidate)
    return result


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source)
            headers = next(reader, None)
            if not headers:
                raise ValueError("The CSV file is empty or has no header row.")
            if len(headers) != len(set(headers)):
                raise ValueError("The file has duplicate header names. Use --normalize-headers to make them unique.")
            rows: list[dict[str, str]] = []
            for line_number, values in enumerate(reader, start=2):
                if len(values) != len(headers):
                    raise ValueError(
                        f"Row {line_number} has {len(values)} values; expected {len(headers)}."
                    )
                rows.append(dict(zip(headers, values)))
            return headers, rows
    except UnicodeDecodeError as error:
        raise ValueError("The file is not UTF-8 encoded. Save it as UTF-8 and try again.") from error
    except csv.Error as error:
        raise ValueError(f"Could not parse the CSV file: {error}") from error


def transform_rows(
    headers: list[str],
    rows: list[dict[str, str]],
    trim: bool,
    normalize_headers: bool,
) -> tuple[list[str], list[dict[str, str]]]:
    output_headers = make_unique_headers(headers) if normalize_headers else headers[:]
    transformed: list[dict[str, str]] = []
    for row in rows:
        values = {header: (row[header].strip() if trim else row[header]) for header in headers}
        transformed.append({new: values[old] for old, new in zip(headers, output_headers)})
    return output_headers, transformed


def find_duplicates(headers: list[str], rows: list[dict[str, str]]) -> tuple[set[int], int]:
    seen: set[tuple[str, ...]] = set()
    duplicate_indices: set[int] = set()
    for index, row in enumerate(rows):
        key = tuple(row[header] for header in headers)
        if key in seen:
            duplicate_indices.add(index)
        else:
            seen.add(key)
    return duplicate_indices, len(duplicate_indices)


def build_report(
    headers: list[str],
    rows: list[dict[str, str]],
    duplicate_count: int,
    required: list[str],
) -> dict[str, object]:
    columns = []
    for header in headers:
        values = [row[header] for row in rows]
        missing = sum(not value.strip() for value in values)
        columns.append({
            "name": header,
            "missing": missing,
            "missing_percent": round((missing / len(rows) * 100) if rows else 0, 1),
            "unique_non_empty": len({value for value in values if value.strip()}),
            "required": header in required,
        })
    return {
        "rows": len(rows),
        "columns": len(headers),
        "duplicate_rows": duplicate_count,
        "required_columns": required,
        "column_report": columns,
    }


def write_csv(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def print_report(report: dict[str, object], as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    print("CSV QUALITY REPORT")
    print("-" * 54)
    print(f"Rows: {report['rows']}    Columns: {report['columns']}    Duplicate rows: {report['duplicate_rows']}")
    print()
    print(f"{'COLUMN':<24} {'MISSING':>9} {'MISSING %':>11} {'UNIQUE':>8} {'REQUIRED':>9}")
    for column in report["column_report"]:
        required = "yes" if column["required"] else "-"
        print(
            f"{column['name']:<24} {column['missing']:>9} "
            f"{column['missing_percent']:>10.1f}% {column['unique_non_empty']:>8} {required:>9}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Summarize missing values and duplicate rows, then optionally write a cleaned CSV."
    )
    parser.add_argument("input", type=Path, help="Path to a UTF-8 CSV file")
    parser.add_argument("--output", type=Path, help="Write a cleaned copy to this path")
    parser.add_argument("--trim", action="store_true", help="Trim leading and trailing spaces from values")
    parser.add_argument("--normalize-headers", action="store_true", help="Convert headers to unique lowercase names")
    parser.add_argument("--drop-duplicates", action="store_true", help="Remove repeated rows in the output copy")
    parser.add_argument("--required", action="append", default=[], metavar="COLUMN", help="Flag blanks in a required column; repeat as needed")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON")
    args = parser.parse_args(argv)
    if (args.trim or args.normalize_headers or args.drop_duplicates) and args.output is None:
        parser.error("cleaning options require --output so the original file stays unchanged")
    if args.drop_duplicates and args.output is None:
        parser.error("--drop-duplicates requires --output")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    input_path = args.input.expanduser().resolve()
    if not input_path.is_file():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        return 2
    output_path = args.output.expanduser().resolve() if args.output else None
    if output_path == input_path:
        print("Error: output must be a different file so the source is preserved.", file=sys.stderr)
        return 2
    try:
        raw_headers, raw_rows = read_csv(input_path)
        headers, rows = transform_rows(raw_headers, raw_rows, args.trim, args.normalize_headers)
        required = args.required
        missing_required = [name for name in required if name not in headers]
        if missing_required:
            print(f"Error: required column not found: {', '.join(missing_required)}", file=sys.stderr)
            return 2
        duplicates, duplicate_count = find_duplicates(headers, rows)
        report = build_report(headers, rows, duplicate_count, required)
        output_rows = [row for index, row in enumerate(rows) if not (args.drop_duplicates and index in duplicates)]
        print_report(report, args.json)
        if output_path is not None:
            write_csv(output_path, headers, output_rows)
            print(f"\nCleaned copy written to: {output_path}")
        return 0
    except (OSError, ValueError, csv.Error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
