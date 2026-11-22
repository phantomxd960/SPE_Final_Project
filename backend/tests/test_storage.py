from regdiff_api.services.storage import safe_name, sha256


def test_safe_name_strips_paths_and_odd_characters():
    assert safe_name("../../etc/passwd") == "passwd"
    assert safe_name("REG 001 v2 (final).md") == "REG_001_v2_final_.md"
    assert safe_name("...") == "document"


def test_sha256_is_stable():
    assert sha256(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
