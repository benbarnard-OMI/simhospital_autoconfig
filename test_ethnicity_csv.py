import os
import csv
import pytest

CSV_PATH = os.path.join(os.path.dirname(__file__), 'ethnicity.csv')

def test_ethnicity_csv_exists():
    """Verify that ethnicity.csv exists."""
    assert os.path.exists(CSV_PATH)

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
