from pathlib import Path


def load_sections(directory: Path) -> list[dict]:
    sections = []
    for path in sorted(directory.glob("*.md")):
        heading = ""
        content = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if content:
                    sections.append({"source": f"{path.name}#{heading}", "text": "\n".join(content).strip()})
                heading, content = line[3:].strip(), [line]
            elif heading:
                content.append(line)
        if content:
            sections.append({"source": f"{path.name}#{heading}", "text": "\n".join(content).strip()})
    if not sections:
        raise ValueError(f"No document sections found in {directory}")
    return sections


class DocumentIndex:
    def __init__(self, directory: Path, model_path: Path):
        from sentence_transformers import SentenceTransformer

        self.sections = load_sections(directory)
        self.embedder = SentenceTransformer(str(model_path), local_files_only=True)
        self.vectors = self.embedder.encode(
            [section["text"] for section in self.sections], normalize_embeddings=True
        )

    def search(self, question: str, limit: int = 3) -> list[dict]:
        query = self.embedder.encode([question], normalize_embeddings=True)[0]
        scores = self.vectors @ query
        ranked = sorted(range(len(scores)), key=lambda index: float(scores[index]), reverse=True)
        return [
            {**self.sections[index], "score": round(float(scores[index]), 3)}
            for index in ranked[:limit]
            if scores[index] >= 0.3
        ]
