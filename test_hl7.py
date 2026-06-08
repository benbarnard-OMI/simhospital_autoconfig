import os
import re
import pytest
import yaml

HL7_YML_PATH = os.path.join(os.path.dirname(__file__), 'hl7.yml')


def test_hl7_yml_exists():
    """Verify that hl7.yml exists."""
    assert os.path.exists(HL7_YML_PATH)


def test_hl7_yml_is_valid_yaml():
    """Verify that hl7.yml is valid YAML."""
    with open(HL7_YML_PATH, 'r') as f:
        data = yaml.safe_load(f)
    assert data is not None


@pytest.fixture
def hl7_yml():
    with open(HL7_YML_PATH, 'r') as f:
        return yaml.safe_load(f)


def test_hl7_top_level_keys(hl7_yml):
    """Verify hl7.yml contains expected top-level sections."""
    required_sections = {
        'allergy', 'diagnosis', 'document', 'procedure',
        'order_control', 'result_status', 'document_status',
        'order_status', 'patient_class', 'gender',
        'mapping', 'primary_facility', 'coding_system',
        'abnormal_flags', 'patient_account_status'
    }
    for section in required_sections:
        assert section in hl7_yml, f"Missing section: {section}"


def test_hl7_allergy_section(hl7_yml):
    """Verify allergy section structure."""
    allergy = hl7_yml['allergy']
    assert 'types' in allergy
    assert isinstance(allergy['types'], list)
    assert len(allergy['types']) > 0

    assert 'severities' in allergy
    assert isinstance(allergy['severities'], list)
    assert len(allergy['severities']) > 0

    assert 'coding_system' in allergy
    assert isinstance(allergy['coding_system'], str)


def test_hl7_document_types_no_duplicates(hl7_yml):
    """Verify document types list has no duplicates."""
    doc_types = hl7_yml['document']['types']
    assert len(doc_types) == len(set(doc_types)), "Duplicate document types found"


def test_hl7_no_plaintext_http_urls(hl7_yml):
    """Verify there are no insecure HTTP URLs in hl7.yml (security check)."""
    raw = yaml.dump(hl7_yml)
    # Look for http:// not followed by localhost/127.0.0.1
    insecure = re.findall(r'http://(?!localhost|127\.0\.0\.0)[^\s"\'<>]+', raw, re.IGNORECASE)
    assert not insecure, f"Insecure HTTP URLs found: {insecure}"


def test_hl7_fhir_mapping_allergy_types_consistent(hl7_yml):
    """Verify FHIR mapping allergy types are consistent with allergy.types."""
    allergy_types = set(hl7_yml['allergy']['types'])
    fhir_allergy_types = set()
    for values in hl7_yml['mapping']['fhir']['allergy_types'].values():
        for v in values:
            fhir_allergy_types.add(v)

    # Check that the 2-char HL7 codes in fhir mapping exist in allergy.types
    hl7_codes_in_mapping = {k for k in fhir_allergy_types if len(k) == 2}
    missing = hl7_codes_in_mapping - allergy_types
    assert not missing, f"FHIR mapping references allergy type codes not defined in allergy.types: {missing}"
