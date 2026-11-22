from regdiff_common.embeddings import MockEmbedder, cosine
from regdiff_common.models import EMBEDDING_DIM


def test_mock_embeddings_are_deterministic_and_normalised():
    embedder = MockEmbedder()
    first, second = embedder.embed(["Report large cash transactions", "Report large cash transactions"])
    assert first == second
    assert len(first) == EMBEDDING_DIM
    assert abs(cosine(first, first) - 1.0) < 1e-9


def test_related_text_scores_higher_than_unrelated_text():
    embedder = MockEmbedder()
    base, related, unrelated = embedder.embed(
        [
            "Institutions must report cash transactions above the reporting threshold.",
            "Cash transactions above the threshold are reported to the authority.",
            "Customers must present a passport for identity verification.",
        ]
    )
    assert cosine(base, related) > cosine(base, unrelated)
