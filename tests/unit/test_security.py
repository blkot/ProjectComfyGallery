from comfy_gallery_core.security import (
    generate_api_token,
    generate_session_material,
    hash_password,
    hash_token,
    verify_password,
)


def test_password_hash_round_trip() -> None:
    encoded = hash_password("correct horse battery staple")

    assert encoded != "correct horse battery staple"
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)


def test_session_material_contains_only_hashable_random_values() -> None:
    material = generate_session_material()

    assert material.session_token_hash == hash_token(material.session_token)
    assert material.csrf_token_hash == hash_token(material.csrf_token)
    assert material.session_token != material.csrf_token


def test_api_token_has_product_prefix() -> None:
    material = generate_api_token()

    assert material.token.startswith("cgpat_")
    assert material.prefix == material.token[:13]
    assert material.token_hash == hash_token(material.token)
