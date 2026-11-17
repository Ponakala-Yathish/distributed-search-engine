from __future__ import annotations

from indexing.tokenizer import tokenize


def normalize_term(term: str) -> str:
    return term.casefold().strip()


def preprocess_query(query: str) -> list[str]:
    if not isinstance(query, str):
        raise TypeError("query must be a string")
    terms: list[str] = []
    seen: set[str] = set()
    for term in tokenize(query):
        if term not in seen:
            seen.add(term)
            terms.append(term)
    return terms
