"""
RAG pipeline: compare two chunking strategies on a small IELTS-prep corpus.

Strategy A (fixed-size): text[i:i+2000], step=2000, no overlap.
Strategy B (recursive):  RecursiveCharacterTextSplitter-style, chunk_size=400,
                         chunk_overlap=80, separators=["\n\n", "\n", ". ", " ", ""].

Retrieval is done with TF-IDF + cosine similarity (scikit-learn).
NOTE on substitution: sentence-transformers was specified in the seminar template,
but installing it in this sandbox requires a ~430MB torch wheel that could not be
downloaded within the available time budget. TF-IDF is used instead as a
lightweight, fully-local embedding/retrieval substitute. The comparison between
chunking strategies (the actual subject of this assignment) is independent of the
embedding backend: both strategies are evaluated with the exact same retriever, so
the relative difference in hit-rate@5 reflects chunking, not the embedding choice.
"""

import json
import os
import re
import glob
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
TOP_K = 5


def load_corpus():
    """Load all .txt documents from data/. Returns dict doc_id -> text."""
    docs = {}
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "*.txt"))):
        fname = os.path.basename(path)
        m = re.match(r"(doc_\d+)_", fname)
        doc_id = m.group(1) if m else os.path.splitext(fname)[0]
        with open(path, "r", encoding="utf-8") as f:
            docs[doc_id] = f.read()
    return docs


# ---------------------------------------------------------------------------
# Strategy A: fixed-size chunking, no overlap
# ---------------------------------------------------------------------------
def fixed_size_chunks(text, chunk_size=2000):
    return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]


# ---------------------------------------------------------------------------
# Strategy B: recursive character splitter (LangChain-style), chunk_size=400,
# overlap=80, separators ["\n\n", "\n", ". ", " ", ""]
# ---------------------------------------------------------------------------
def _merge_splits(splits, separator, chunk_size, chunk_overlap):
    chunks = []
    current = []
    total = 0
    sep_len = len(separator)

    for s in splits:
        s_len = len(s)
        if total + s_len + (sep_len if current else 0) > chunk_size and current:
            chunk = separator.join(current)
            if chunk:
                chunks.append(chunk)
            # shrink window from the front until it fits within overlap budget
            while total > chunk_overlap or (
                total + s_len + (sep_len if current else 0) > chunk_size and total > 0
            ):
                total -= len(current[0]) + (sep_len if len(current) > 1 else 0)
                current = current[1:]
        current.append(s)
        total += s_len + (sep_len if len(current) > 1 else 0)

    chunk = separator.join(current)
    if chunk:
        chunks.append(chunk)
    return chunks


def recursive_split(text, chunk_size=400, chunk_overlap=80,
                     separators=("\n\n", "\n", ". ", " ", "")):
    sep = separators[0]
    rest = separators[1:]
    parts = list(text) if sep == "" else text.split(sep)

    good_parts = []
    for p in parts:
        if len(p) < chunk_size:
            good_parts.append(p)
        elif rest:
            good_parts.extend(recursive_split(p, chunk_size, chunk_overlap, rest))
        else:
            good_parts.append(p)

    return _merge_splits(good_parts, sep, chunk_size, chunk_overlap)


# ---------------------------------------------------------------------------
# Build chunk index for a given strategy
# ---------------------------------------------------------------------------
def build_chunks(docs, strategy):
    chunks = []  # list of dicts: {chunk_id, doc_id, text}
    for doc_id, text in docs.items():
        if strategy == "fixed":
            pieces = fixed_size_chunks(text, chunk_size=2000)
        elif strategy == "recursive":
            pieces = recursive_split(text, chunk_size=400, chunk_overlap=80)
        else:
            raise ValueError(strategy)
        for i, p in enumerate(pieces):
            p = p.strip()
            if p:
                chunks.append({"chunk_id": f"{doc_id}_c{i}", "doc_id": doc_id, "text": p})
    return chunks


# ---------------------------------------------------------------------------
# Retrieval (TF-IDF cosine similarity)
# ---------------------------------------------------------------------------
def build_retriever(chunks):
    vectorizer = TfidfVectorizer(lowercase=True, stop_words="english", ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([c["text"] for c in chunks])
    return vectorizer, matrix


def retrieve(query, vectorizer, matrix, chunks, top_k=TOP_K):
    qvec = vectorizer.transform([query])
    sims = cosine_similarity(qvec, matrix)[0]
    ranked_idx = sims.argsort()[::-1][:top_k]
    results = []
    for idx in ranked_idx:
        c = chunks[idx]
        results.append({"chunk_id": c["chunk_id"], "doc_id": c["doc_id"],
                         "score": float(sims[idx]), "text": c["text"]})
    return results


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
def evaluate(gold, vectorizer, matrix, chunks, top_k=TOP_K):
    per_question = []
    hits = 0
    all_hits = 0
    for item in gold:
        results = retrieve(item["question"], vectorizer, matrix, chunks, top_k)
        retrieved_docs = [r["doc_id"] for r in results]
        gold_sources = set(item["gold_sources"])
        retrieved_set = set(retrieved_docs)
        hit = 1 if gold_sources & retrieved_set else 0
        all_hit = 1 if gold_sources <= retrieved_set else 0
        hits += hit
        all_hits += all_hit
        per_question.append({
            "id": item["id"],
            "type": item["type"],
            "question": item["question"],
            "gold_sources": item["gold_sources"],
            "retrieved_docs": retrieved_docs,
            "retrieved_chunks": [r["chunk_id"] for r in results],
            "hit@5": hit,
            "all_sources_hit@5": all_hit,
        })
    hit_rate = hits / len(gold)
    all_hit_rate = all_hits / len(gold)
    return hit_rate, all_hit_rate, per_question


def main():
    docs = load_corpus()
    with open(os.path.join(DATA_DIR, "gold.json"), "r", encoding="utf-8") as f:
        gold = json.load(f)

    print(f"Corpus: {len(docs)} documents, "
          f"{sum(len(t) for t in docs.values())} characters total\n")

    report = {}
    for strategy in ["fixed", "recursive"]:
        chunks = build_chunks(docs, strategy)
        vectorizer, matrix = build_retriever(chunks)
        hit_rate, all_hit_rate, per_question = evaluate(gold, vectorizer, matrix, chunks)
        report[strategy] = {
            "num_chunks": len(chunks),
            "avg_chunk_len": sum(len(c["text"]) for c in chunks) / len(chunks),
            "hit_rate@5": hit_rate,
            "all_sources_hit_rate@5": all_hit_rate,
            "per_question": per_question,
        }
        print(f"=== Strategy: {strategy} ===")
        print(f"  chunks: {len(chunks)}, avg chunk length: {report[strategy]['avg_chunk_len']:.1f} chars")
        print(f"  hit-rate@5 (any gold doc):  {hit_rate:.3f}")
        print(f"  hit-rate@5 (all gold docs): {all_hit_rate:.3f}\n")

    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Per-question comparison table
    print(f"{'id':<4}{'type':<22}{'fixed any':<11}{'fixed all':<11}{'rec any':<10}{'rec all':<10}")
    for q_fixed, q_rec in zip(report["fixed"]["per_question"], report["recursive"]["per_question"]):
        print(f"{q_fixed['id']:<4}{q_fixed['type']:<22}{q_fixed['hit@5']:<11}{q_fixed['all_sources_hit@5']:<11}"
              f"{q_rec['hit@5']:<10}{q_rec['all_sources_hit@5']:<10}")


if __name__ == "__main__":
    main()
