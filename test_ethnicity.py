import os
import csv
import pytest

ETHNICITY_CSV_PATH = os.path.join(os.path.dirname(__file__), 'ethnicity.csv')


def test_ethnicity_csv_exists():
    """Verify that ethnicity.csv exists."""
    assert os.path.exists(ETHNICITY_CSV_PATH)


def test_ethnicity_csv_has_correct_columns():
    """Verify ethnicity.csv has the expected 3 columns per row."""
    with open(ETHNICITY_CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader, 1):
            # Skip comment rows and blank rows
            if not row or (row and row[0].startswith('#')):
                continue
            assert len(row) == 3, \
                f"Row {i} should have 3 columns (id, text, frequency), got {len(row)}: {row}"


def test_ethnicity_csv_entries_have_string_id():
    """Verify that each non-comment row has a non-empty string ID."""
    with open(ETHNICITY_CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader, 1):
            if not row or (row and row[0].startswith('#')):
                continue
            entry_id, text, freq = row
            assert isinstance(entry_id, str) and len(entry_id) > 0, \
                f"Row {i}: ID must be a non-empty string, got: {entry_id!r}"


def test_ethnicity_csv_entries_have_string_text():
    """Verify that each non-comment row has a non-empty string description."""
    with open(ETHNICITY_CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader, 1):
            if not row or (row and row[0].startswith('#')):
                continue
            entry_id, text, freq = row
            assert isinstance(text, str) and len(text) > 0, \
                f"Row {i} (id={entry_id}): text must be a non-empty string, got: {text!r}"


def test_ethnicity_csv_entries_have_integer_frequency():
    """Verify that each non-comment row has an integer frequency."""
    with open(ETHNICITY_CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader, 1):
            if not row or (row and row[0].startswith('#')):
                continue
            entry_id, text, freq = row
            assert freq.lstrip('-').isdigit(), \
                f"Row {i} (id={entry_id}): frequency must be an integer, got: {freq!r}"


def test_ethnicity_csv_ids_unique():
    """Verify that all entry IDs are unique."""
    seen_ids = []
    with open(ETHNICITY_CSV_PATH, 'r') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader, 1):
            if not row or (row and row[0].startswith('#')):
                continue
            entry_id = row[0]
            assert entry_id not in seen_ids, \
                f"Duplicate ID found: {entry_id}"
            seen_ids.append(entry_id)
