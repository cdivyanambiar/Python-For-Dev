"""05 - RAG (Retrieval-Augmented Generation) from scratch.

Run: py 05_rag_basics.py

RAG = an OPEN-BOOK EXAM for an AI:
  1. Retrieve : find the pages in your documents related to the question.
  2. Augment  : paste those pages into the LLM prompt.
  3. Generate : the LLM writes an answer using ONLY those pages.
Why? LLMs don't know your company's private docs and sometimes MAKE THINGS UP (hallucinate).
RAG grounds them in real text and lets them CITE SOURCES.

    INDEXING (offline):  docs -> chunk -> embed -> vector store
    QUERY    (online) :  question -> embed -> top-k similarity search -> prompt(context + question) -> LLM

This file runs without any API key:
  - Embeddings use TF-IDF (word-based vectors). In production use a semantic embedding model,
    e.g. sentence-transformers "all-MiniLM-L6-v2" or OpenAI "text-embedding-3-small".
  - The vector store is a NumPy matrix with brute-force cosine search. In production use FAISS,
    Chroma, pgvector, Pinecone, etc. (approximate nearest neighbour search such as HNSW).
  - The "LLM" is a stub that picks the best-matching sentence from the context. A real LLM call is
    shown in `call_real_llm` for reference.

Interview: ways to improve this basic RAG
  - semantic embeddings instead of TF-IDF
  - hybrid search: keyword (BM25) + vector search together
  - re-ranking: a second, more accurate model re-orders the top results
  - metadata filters (team, date, doc type)
  - evaluation: did we retrieve the right chunk (recall@k)? is the answer supported by the context
    (faithfulness)? e.g. with RAGAS
"""
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

# Device docs live as Markdown files in rag_docs/ (one per customer area). Each file starts with a small
# "front matter" header (between --- lines) holding metadata, e.g. "org: acme" = who may see this doc.
DOCS_DIR = Path(__file__).parent / "rag_docs"

# Shared SRE runbooks, visible to every customer (org = "shared"). In real life: PDFs, Confluence pages, ...
DOCUMENTS = {
    "runbook_cpu.md": (
        "High CPU alert runbook. When CPU usage stays above 90 percent for 10 minutes, first check the top "
        "processes with top or htop. If a single Java process is responsible, capture a thread dump with jstack. "
        "Scale out the deployment by adding replicas if the load is legitimate traffic."
    ),
    "runbook_disk.md": (
        "Disk full runbook. When disk usage exceeds 85 percent, find large files with du -sh. "
        "Rotate and compress old logs using logrotate. Old Docker images can be removed with docker image prune. "
        "If the volume keeps growing, request a larger persistent volume."
    ),
    "policy_oncall.md": (
        "On-call policy. Sev1 incidents must be acknowledged within 5 minutes and the incident commander paged. "
        "Sev2 incidents must be acknowledged within 30 minutes. Every Sev1 needs a postmortem within 3 business days."
    ),
    "kafka_notes.md": (
        "Kafka consumer lag happens when consumers process messages slower than producers write them. "
        "To reduce lag, add consumers up to the number of partitions, increase max.poll.records, or "
        "optimise the processing code. Monitor lag per partition with Burrow or kafka-consumer-groups."
    ),
}


# @dataclass auto-generates __init__ / __repr__ / __eq__ from the fields below.
@dataclass
class Chunk:
    """A piece of a document plus metadata, so answers can cite their source."""
    doc_id: str                                     # which file it came from -> lets the answer say WHERE
    text: str
    org: str = "shared"                             # METADATA: which customer may see it ("shared" = everyone)


def load_markdown_docs(folder: Path) -> list[tuple[str, str, str]]:
    """Read every .md file -> (doc_id, org, plain text). Real loaders: LangChain / LlamaIndex document loaders."""
    docs = []
    for path in sorted(folder.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        meta = re.match(r"---\s*\norg:\s*(\w+)\s*\n---\s*\n", raw)    # parse the front matter header
        org = meta.group(1) if meta else "shared"
        body = raw[meta.end():] if meta else raw
        # drop Markdown headings ("# Title") and join paragraphs into plain text for chunking
        text = " ".join(line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#"))
        docs.append((path.name, org, text))
    return docs


def split_sentences(text: str) -> list[str]:
    """Naive sentence splitter (real systems use nltk/spaCy or token-based splitters)."""
    return [s.strip().rstrip(".") + "." for s in text.split(". ") if s.strip()]


def chunk_text(doc_id: str, text: str, sentences_per_chunk: int = 2, overlap: int = 1,
               org: str = "shared") -> list[Chunk]:
    """Group sentences into chunks. Overlap repeats a sentence in the next chunk so context isn't cut mid-idea."""
    # Why chunk? Docs can be huge, LLM prompts have a size limit, and small pieces make search more precise.
    # With 2 sentences per chunk and 1 overlap: chunk1 = s1+s2, chunk2 = s2+s3, chunk3 = s3+s4, ...
    # Real systems usually chunk by TOKENS (e.g. 500 tokens with 50 overlap).
    sents = split_sentences(text)
    step = sentences_per_chunk - overlap
    return [Chunk(doc_id, " ".join(sents[i:i + sentences_per_chunk]), org)
            for i in range(0, max(len(sents) - overlap, 1), step)]


class VectorStore:
    """Minimal in-memory vector DB: holds chunk embeddings and returns the most similar chunks."""
    # EMBEDDING = turning text into a list of numbers (vector) so the computer can measure similarity.
    # COSINE SIMILARITY = imagine each text as an arrow: same direction = similar topic (~1),
    # right angle = unrelated (0).
    # Real systems use a vector DB (FAISS, Chroma, pgvector, Pinecone) to search millions of chunks fast.

    def __init__(self) -> None:
        """Start empty; call add() to index chunks."""
        # TF-IDF scores each word: HIGH if it appears in this chunk but is RARE overall (e.g. "docker"),
        # LOW for words that are everywhere. stop_words="english" ignores filler words (the, is, and).
        # Limitation: TF-IDF matches WORDS, not MEANING ("car" vs "automobile" look unrelated).
        self.embedder = TfidfVectorizer(stop_words="english")
        self.chunks: list[Chunk] = []
        self.matrix: np.ndarray | None = None

    def add(self, chunks: list[Chunk]) -> None:
        """Embed all chunks and L2-normalise them so a dot product equals cosine similarity."""
        self.chunks = chunks
        # fit_transform = learn the vocabulary AND convert every chunk into a vector
        vectors = self.embedder.fit_transform([c.text for c in chunks]).toarray()
        # normalise each vector to length 1 -> a simple dot product then equals cosine similarity
        self.matrix = vectors / (np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9)

    def search(self, query: str, k: int = 3, org: str = "shared") -> list[tuple[Chunk, float]]:
        """Embed the query the same way, score every chunk by cosine similarity, return the top-k for this org."""
        q = self.embedder.transform([query]).toarray()[0]   # transform (NOT fit again) = same vocabulary
        q = q / (np.linalg.norm(q) + 1e-9)
        scores = self.matrix @ q                    # similarity of the question with EVERY chunk at once
        # METADATA FILTER (tenant isolation): chunks of other customers get a score of -1, so they can
        # never reach the prompt. Real vector DBs do this with a filter, e.g. where={"org": "acme"}.
        allowed = np.array([c.org in (org, "shared") for c in self.chunks])
        scores = np.where(allowed, scores, -1.0)
        top = np.argsort(scores)[::-1][:k]          # sort, reverse (highest first), keep top k
        return [(self.chunks[i], float(scores[i])) for i in top]


def build_prompt(question: str, retrieved: list[tuple[Chunk, float]]) -> str:
    """Augment step: put retrieved context into the prompt and tell the LLM to answer only from it."""
    # Instructions ("ONLY from context", "say I don't know", "cite [1]") reduce hallucination.
    context = "\n".join(f"[{i + 1}] ({c.doc_id}) {c.text}" for i, (c, _) in enumerate(retrieved))
    return (
        "You are an SRE assistant. Answer ONLY using the context below. "
        "If the answer is not in the context, say \"I don't know\". Cite sources like [1].\n\n"
        f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"
    )


# Filler words removed from the question so they don't count as matches.
STOP_WORDS = {"how", "do", "i", "can", "what", "is", "the", "a", "an", "from", "must", "be", "to", "up", "of"}


def fake_llm(question: str, retrieved: list[tuple[Chunk, float]], min_score: float = 0.2) -> str:
    """Stand-in for an LLM: an extractive answer made of the 2 context sentences that best match the question."""
    # A real LLM writes a fluent answer in its own words; this one just copies the best-matching
    # sentences (an EXTRACTIVE answer) so the demo runs without an API key.
    if not retrieved or retrieved[0][1] < min_score:    # guardrail: nothing relevant retrieved -> don't guess
        # min_score is tuned on real questions: weak matches on one common word (e.g. "data") score ~0.1
        return "I don't know based on the available documents."
    q_words = set(question.lower().replace("?", "").split()) - STOP_WORDS
    scored, seen = [], set()
    for i, (chunk, _) in enumerate(retrieved):
        for sentence in split_sentences(chunk.text):
            if sentence in seen:                    # overlapping chunks repeat sentences
                continue
            seen.add(sentence)
            # score = how many question words the sentence contains
            overlap = len(q_words & set(sentence.lower().replace(",", "").rstrip(".").split()))
            scored.append((overlap, sentence, i + 1))
    best = sorted(scored, key=lambda t: -t[0])[:2]  # 2 best sentences, with their source number [1]/[2]
    return " ".join(f"{s} [{src}]" for _, s, src in best)


def call_real_llm(prompt: str) -> str:
    """Reference only (not called): the Generate step with a real LLM, e.g. OpenAI.

    from openai import OpenAI
    client = OpenAI()                     # reads OPENAI_API_KEY from the environment (never hard-code keys)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        temperature=0,                    # low temperature = factual, repeatable answers
    )
    return resp.choices[0].message.content
    """
    raise NotImplementedError("Plug in your LLM provider here.")


def main() -> None:
    # INDEXING: shared runbooks (dict above) + device docs (rag_docs/*.md) -> chunks -> vectors
    print("=== INDEXING: chunk + embed + store ===")
    chunks = [c for doc_id, text in DOCUMENTS.items() for c in chunk_text(doc_id, text)]
    md_docs = load_markdown_docs(DOCS_DIR)
    chunks += [c for doc_id, org, text in md_docs for c in chunk_text(doc_id, text, org=org)]
    store = VectorStore()
    store.add(chunks)
    print(f"{len(DOCUMENTS)} runbooks + {len(md_docs)} markdown docs -> {len(chunks)} chunks "
          f"-> embedding matrix {store.matrix.shape}")

    user_org = "acme"                               # comes from the LOGIN SESSION, never from the question
    print(f"Logged-in org: {user_org} (sees 'shared' + '{user_org}' docs only)\n")

    questions = [
        "How do I clean up disk space from old docker images?",
        "How fast must a Sev1 incident be acknowledged?",
        "How can I reduce Kafka consumer lag?",
        "What is the office wifi password?",          # not in the docs -> should say I don't know
        "Why is gw-1 offline?",                       # answered from rag_docs/acme_gateways.md
        "Which switch has a noisy fan?",              # answered from rag_docs/acme_switches.md
        "What does the note on gw-2 say?",            # prompt injection inside a doc: shown as text, never obeyed
        "What secret data does Globex have?",         # globex doc exists but is filtered out for acme
    ]
    # QUERY: for each question -> retrieve top 2 chunks (this org only) -> (show prompt for the first) -> answer
    for q in questions:
        print("=" * 80)
        print("Q:", q)
        retrieved = store.search(q, k=2, org=user_org)
        for c, score in retrieved:
            print(f"   retrieved score={score:.2f}  {c.doc_id}: {c.text[:70]}...")
        if q == questions[0]:
            print("\n--- Prompt sent to the LLM ---\n" + build_prompt(q, retrieved) + "\n------------------------------")
        print("A:", fake_llm(q, retrieved))


if __name__ == "__main__":
    main()
