from orchestrator.storage import slugify

def test_slugify_vietnamese():
    assert slugify("Đắc Kỷ Trụ Vương") == "dac_ky_tru_vuong"

def test_slugify_special_chars():
    assert slugify("Hello @ World! - 123") == "hello_world_123"

def test_slugify_multiple_spaces_and_underscores():
    assert slugify("A   B___C- -D") == "a_b_c_d"

def test_slugify_trim_underscores():
    assert slugify("_Hello_World_") == "hello_world"
    assert slugify("___A___") == "a"

def test_slugify_all_special_chars():
    assert slugify("!@#$%^&*()") == "unknown"
    assert slugify("   ") == "unknown"

def test_slugify_empty_string():
    assert slugify("") == "unknown"
    assert slugify(None) == "unknown"
