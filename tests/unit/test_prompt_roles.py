from comfy_gallery_api.routes.evaluations import _prompt_role_rank


def test_review_prompt_roles_order_positive_before_unknown_and_negative() -> None:
    roles = ["negative", None, "positive", "main", "custom"]

    assert sorted(roles, key=_prompt_role_rank) == [
        "positive",
        "main",
        None,
        "custom",
        "negative",
    ]
