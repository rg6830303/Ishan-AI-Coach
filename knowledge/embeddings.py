import os
import json
import numpy as np
from config import CORPUS_PATH, INDEX_PATH


def load_and_chunk_corpus() -> list[dict]:
    """Load all corpus .md files and chunk by ## headers."""
    chunks = []
    for filename in os.listdir(CORPUS_PATH):
        if not filename.endswith(".md"):
            continue
        tier_tag = filename.replace(".md", "")
        filepath = os.path.join(CORPUS_PATH, filename)

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        sections = content.split("\n## ")
        for i, section in enumerate(sections):
            if i == 0:
                lines = section.strip().split("\n")
                title = lines[0].replace("# ", "").strip()
                body = "\n".join(lines[1:]).strip()
            else:
                lines = section.strip().split("\n")
                title = lines[0].strip()
                body = "\n".join(lines[1:]).strip()

            if len(body) < 50:
                continue

            subsections = body.split("\n### ")
            if len(subsections) > 1:
                for j, sub in enumerate(subsections):
                    if j == 0 and len(sub.strip()) < 50:
                        continue
                    sub_lines = sub.strip().split("\n")
                    sub_title = sub_lines[0].strip() if j > 0 else title
                    sub_body = "\n".join(sub_lines[1:]).strip() if j > 0 else sub.strip()
                    if len(sub_body) < 30:
                        continue
                    chunks.append({
                        "id": f"{tier_tag}_{i}_{j}",
                        "title": f"{title} > {sub_title}" if j > 0 else title,
                        "content": sub_body,
                        "tier_tag": tier_tag,
                        "source": filename,
                    })
            else:
                chunks.append({
                    "id": f"{tier_tag}_{i}",
                    "title": title,
                    "content": body,
                    "tier_tag": tier_tag,
                    "source": filename,
                })

    return chunks


def build_index():
    """Build FAISS index from corpus chunks."""
    try:
        from sentence_transformers import SentenceTransformer
        import faiss
    except ImportError:
        print("Please install: pip install sentence-transformers faiss-cpu")
        return

    print("Loading corpus...")
    chunks = load_and_chunk_corpus()
    print(f"Found {len(chunks)} chunks")

    print("Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    texts = [f"{c['title']}\n{c['content']}" for c in chunks]
    print("Encoding chunks...")
    embeddings = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)

    dimension = embeddings.shape[1]
    index = faiss.IndexFlatIP(dimension)
    index.add(np.array(embeddings).astype("float32"))

    os.makedirs(INDEX_PATH, exist_ok=True)
    faiss.write_index(index, os.path.join(INDEX_PATH, "coach.index"))

    with open(os.path.join(INDEX_PATH, "chunks.json"), "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2)

    print(f"Index built: {len(chunks)} chunks, dimension={dimension}")
    print(f"Saved to: {INDEX_PATH}")


if __name__ == "__main__":
    build_index()
