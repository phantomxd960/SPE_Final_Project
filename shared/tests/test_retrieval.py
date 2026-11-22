from regdiff_common.retrieval import RRF_K, reciprocal_rank_fusion


def test_item_ranked_well_in_both_lists_wins():
    scores = reciprocal_rank_fusion([[1, 2, 3], [2, 1, 4]])
    ranked = sorted(scores, key=scores.get, reverse=True)
    assert set(ranked[:2]) == {1, 2}
    assert ranked[-1] in {3, 4}


def test_scores_follow_the_rrf_formula():
    scores = reciprocal_rank_fusion([[7], [9, 7]])
    assert scores[7] == 1 / (RRF_K + 1) + 1 / (RRF_K + 2)
    assert scores[9] == 1 / (RRF_K + 1)


def test_empty_rankings_give_no_scores():
    assert reciprocal_rank_fusion([[], []]) == {}
