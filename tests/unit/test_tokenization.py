from __future__ import annotations

from indexing.tokenizer import clean_wiki_markup, tokenize


def test_tokenizer_normalizes_case_and_punctuation() -> None:
    assert tokenize("Hello, WORLD!") == ["hello", "world"]


def test_tokenizer_removes_wiki_markup() -> None:
    text = "'''April''' is a [[month]] in the [[Julian calendar|Julian]] year."
    assert clean_wiki_markup(text) == "April is a month in the Julian year."
    assert tokenize(text) == ["april", "is", "a", "month", "in", "the", "julian", "year"]


def test_tokenizer_splits_underscores_like_the_distributed_index() -> None:
    assert tokenize("Simple_English Wikipedia") == ["simple", "english", "wikipedia"]


def test_tokenizer_handles_unicode_case_folding() -> None:
    assert tokenize("Straße GROSS") == ["strasse", "gross"]
