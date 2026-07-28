from roster_engine.cover_repository import (
    classify_cover_category,
)


def test_dollar_fc_maps_to_fc_category() -> None:
    assert (
        classify_cover_category("$FC")
        == "FC"
    )


def test_plain_fc_maps_to_fc_category() -> None:
    assert (
        classify_cover_category("FC")
        == "FC"
    )


def test_gp_and_gx_keep_their_categories() -> None:
    assert (
        classify_cover_category("GP")
        == "GP"
    )
    assert (
        classify_cover_category("GX")
        == "GX"
    )


def test_normal_cover_is_non_fc() -> None:
    assert (
        classify_cover_category("$S IPPT")
        == "NON_FC"
    )