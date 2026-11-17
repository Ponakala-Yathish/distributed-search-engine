"""Unicode-aware text cleanup and tokenization."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

_COMMENT_PATTERN = re.compile(r"<!--.*?-->", re.DOTALL)
_HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
_WIKI_LINK_PATTERN = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_MARKDOWN_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_REFERENCE_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\[[^\]]*\]")
_HEADING_PATTERN = re.compile(r"^\s{0,3}={1,6}\s*|\s*={1,6}\s*$", re.MULTILINE)
_BOLD_ITALIC_PATTERN = re.compile(r"'{2,3}|_{2,3}|\*{2,}")
_PUNCTUATION_PATTERN = re.compile(r"[^\w]+", re.UNICODE)
_UNDERSCORE_PATTERN = re.compile(r"_")


def clean_wiki_markup(text: str) -> str:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    value = _COMMENT_PATTERN.sub(" ", text)
    value = _HTML_TAG_PATTERN.sub(" ", value)
    previous = None
    while previous != value:
        previous = value
        value = _WIKI_LINK_PATTERN.sub(lambda match: match.group(2) or match.group(1), value)
    value = _MARKDOWN_LINK_PATTERN.sub(r"\1", value)
    value = _REFERENCE_LINK_PATTERN.sub(r"\1", value)
    value = _HEADING_PATTERN.sub(" ", value)
    value = _BOLD_ITALIC_PATTERN.sub(" ", value)
    return " ".join(value.split())


def tokenize(text: str) -> list[str]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    normalized = unicodedata.normalize("NFKC", clean_wiki_markup(text)).casefold()
    normalized = _UNDERSCORE_PATTERN.sub(" ", normalized)
    normalized = _PUNCTUATION_PATTERN.sub(" ", normalized)
    return [token for token in normalized.split() if token]


def tokenize_dataframe(documents: Any, text_column: str = "text", output_column: str = "tokens") -> Any:
    from pyspark.sql.functions import coalesce, lit, udf
    from pyspark.sql.types import ArrayType, StringType

    tokenizer = udf(tokenize, ArrayType(StringType()))
    return documents.withColumn(output_column, tokenizer(coalesce(documents[text_column], lit(""))))


def main() -> int:
    import argparse
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Tokenize a text file with Unicode-aware normalization")
    parser.add_argument("source", help="UTF-8 text file")
    parser.add_argument("--output", default=None, help="Write one JSON token array per line")
    args = parser.parse_args()
    text = Path(args.source).read_text(encoding="utf-8")
    tokens = tokenize(text)
    if args.output:
        with Path(args.output).open("w", encoding="utf-8") as stream:
            stream.write(json.dumps(tokens, ensure_ascii=False))
    else:
        print(json.dumps(tokens, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
