# Algorithms

## Tokenization

`indexing/tokenizer.py` applies Unicode NFKC normalization, case folding, HTML/comment removal, Wikipedia link-label extraction, Markdown link-label extraction, heading/bold cleanup, underscore separation, and punctuation separation. The query tokenizer uses the same implementation so index and query terms remain consistent.

## BM25

For query term `t` and document `d`:

```text
BM25(d,Q) = sum IDF(t) * TF(t,d) * (k1 + 1)
                    / (TF(t,d) + k1 * (1 - b + b * len(d) / avgdl))
```

- `k1 = 1.2`
- `b = 0.75`
- `IDF(t) = ln(1 + (N - DF(t) + 0.5) / (DF(t) + 0.5))`

Spark computes document frequency and IDF from distributed postings. The API retrieves only postings for query terms, calculates BM25 for candidates, and never scans every document.

## Hybrid Ranking

For the candidate result set:

```text
FinalScore = 0.7 * (BM25 / maximumCandidateBM25)
           + 0.3 * (PageRank / maximumCandidatePageRank)
```

The maximum is computed across the full candidate set before pagination. This makes scores consistent between pages. A zero maximum contributes zero.

## PageRank

The distributed algorithm operates on document-ID vertices and valid link edges.

For each iteration:

```text
PR(d) = (1 - damping) / N
      + damping * (sum(PR(src) / outDegree(src)) + danglingMass / N)
```

- Dangling nodes have no outgoing valid edge.
- Dangling probability mass is redistributed uniformly.
- Invalid links are removed during graph construction.
- The default is 15 iterations, above the required minimum of 10.
- Convergence uses an L1 score delta and the configured tolerance.

The Spark implementation performs joins, aggregations, and score updates on distributed DataFrames. It does not transfer the graph to the driver.

## Iceberg Idempotency

The logical key is `doc_id`. A MERGE updates or deletes a row only when the source version is at least the stored version. New documents are inserted. Phase defaults guarantee that a repeated phase cannot overwrite a newer phase with an older version.

## Export Atomicity

1. Spark writes all Parquet datasets into a new immutable version directory.
2. Metadata is written only after the datasets complete.
3. Schemas, counts, and PageRank completeness are validated.
4. The export is uploaded to a new HDFS version path.
5. VM4 downloads to a temporary location and validates it again.
6. The local `current` symlink is atomically replaced.

A failure at any step leaves the prior serving version untouched.
