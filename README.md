# CSV Quality Checker

A Python command-line tool for getting a quick, repeatable quality report before working with a CSV file. It reports missing values, unique non-empty values, and duplicate rows; optional cleaning writes a separate copy so the input remains untouched.

## Features

- Read UTF-8 CSV files, including files with a UTF-8 byte-order mark.
- Report row and column counts, missing-cell counts and percentages, and unique non-empty values per column.
- Detect repeated rows and optionally remove repeats from an output copy.
- Optionally trim whitespace and normalize headers to unique lowercase names.
- Mark one or more columns as required and report their blank values.
- Print a readable terminal summary or JSON for another script to consume.
- Reject malformed rows and never overwrite the input file.

## Try the sample

Requires Python 3.10 or newer. No third-party packages are needed.

```bash
python csv_quality.py data/sample_leads.csv --required Email --json
python csv_quality.py data/sample_leads.csv --trim --normalize-headers --drop-duplicates --output cleaned_leads.csv
```

The sample contains a repeated row, a missing email, whitespace, and two similarly named City columns. Use `--normalize-headers` to turn them into unique names (`city`, `city_2`).

## Options

Run `python csv_quality.py --help` to see all options. Cleaning flags require `--output`; the source CSV is never modified.

## Built with

Python standard library: `argparse`, `csv`, `json`, `pathlib`, and `re`.
