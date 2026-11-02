import os
import csv
import pytest

CSV_PATH = os.path.join(os.path.dirname(__file__), 'ethnicity.csv')


def test_ethnicity_csv_valid_data():
    """Verify the data format in ethnicity.csv."""
    with open(CSV_PATH, 'r', newline='') as f:
        reader = csv.reader(f)
        for row_num, row in enumerate(reader, start=1):
            # Skip empty lines or commented lines
            if not row or row[0].startswith('#'):
                continue

            # Verify exactly 3 columns
            assert len(row) == 3, f"Row {row_num} does not have exactly 3 columns: {row}"

            # Verify data types
            id_col, text_col, freq_col = row

            assert isinstance(id_col, str), f"Row {row_num} ID is not a string: {id_col}"
            assert isinstance(text_col, str), f"Row {row_num} Text is not a string: {text_col}"

            # Frequency should be convertible to int
            try:
                int(freq_col)
            except ValueError:
                pytest.fail(f"Row {row_num} Frequency is not a valid integer: {freq_col}")


def test_ethnicity_csv_sentinel_invariants():
    """Verify the nil,nil sentinel row invariants."""
    rows = []
    with open(CSV_PATH, 'r', newline='') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or row[0].startswith('#'):
                continue
            rows.append(row)

    # Exactly one row has id == "nil" and text == "nil"
    sentinel_rows = [row for row in rows if row[0] == "nil" and row[1] == "nil"]
    assert len(sentinel_rows) == 1, f"Expected exactly one sentinel row, found {len(sentinel_rows)}: {sentinel_rows}"

    # No other row has id == "nil" or text == "nil"
    nil_rows = [row for row in rows if row[0] == "nil" or row[1] == "nil"]
    assert len(nil_rows) == 1, f"Expected exactly one row with nil values, found {len(nil_rows)}: {nil_rows}"

    # All frequency values (including sentinel) are positive integers
    for row in rows:
        freq = int(row[2])
        assert freq > 0, f"Frequency must be a positive integer, got {freq} in row {row}"
