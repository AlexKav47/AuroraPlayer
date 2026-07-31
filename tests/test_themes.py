from aurora_player.app import BUILTIN_THEMES


def test_new_theme_names_and_requested_palette_colours() -> None:
    assert BUILTIN_THEMES["pixie"]["label"] == "Pixie"
    assert {
        "#C5B3D3",
        "#F5CBCB",
        "#FFE2E2",
        "#FBEFEF",
    }.issubset(BUILTIN_THEMES["pixie"].values())

    assert BUILTIN_THEMES["retro"]["label"] == "Retro"
    assert {
        "#EAECF0",
        "#FE7F2D",
        "#233D4D",
        "#000000",
    }.issubset(BUILTIN_THEMES["retro"].values())

    assert BUILTIN_THEMES["space"]["label"] == "Space"
    assert {
        "#B5B9F0",
        "#408175",
        "#2E4540",
        "#0B0909",
    }.issubset(BUILTIN_THEMES["space"].values())


def test_every_builtin_theme_provides_the_base_qss_roles() -> None:
    required_roles = {
        "label",
        "window",
        "panel",
        "panel_alt",
        "control",
        "control_hover",
        "text",
        "muted",
        "border",
        "accent",
        "accent_hover",
        "selection_text",
    }
    for palette in BUILTIN_THEMES.values():
        assert required_roles == palette.keys()
