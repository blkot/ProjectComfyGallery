from comfy_gallery_core.config import Settings


def test_allowed_origins_are_normalized() -> None:
    settings = Settings(
        allowed_origins="http://localhost:8080, http://localhost:5173,",
    )

    assert settings.allowed_origin_list == [
        "http://localhost:8080",
        "http://localhost:5173",
    ]


def test_comfyui_user_is_optional_and_trimmed() -> None:
    assert Settings(comfyui_user="  operator ").comfyui_user == "operator"
    assert Settings(comfyui_user="   ").comfyui_user is None
