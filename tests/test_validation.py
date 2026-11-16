from watchlist_app import validation


def test_similar_ids_keep_only_plain_tmdb_ids():
    film = validation.clean_film({"title": "Heat", "similar_ids": [11, "12", True, -3, 13, 10**12]})
    assert film["similar_ids"] == [11, 13]
    assert validation.clean_film({"title": "Heat", "similar_ids": "11"})["similar_ids"] == []
