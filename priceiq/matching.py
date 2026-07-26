"""AI product matching: match my catalog to competitor listings by meaning,
so "A Light in the Attic" matches "Light in the Attic, The (Silverstein)" even
though the titles differ. Uses local sentence-embeddings (no API key).
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any

DEFAULT_MODEL = "all-MiniLM-L6-v2"


@dataclass
class Match:
    listing: Any  # sources.Listing
    score: float


@lru_cache(maxsize=2)
def _load_model(name: str):
    # Imported lazily so the module is importable without the (heavy) dependency.
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(name)


def match_catalog(my_products: list, listings: list,
                  model_name: str = DEFAULT_MODEL, threshold: float = 0.55) -> dict:
    """Return {sku: [Match, ...]} — listings above `threshold`, best first.

    Cosine similarity on normalized embeddings, so scores are in [-1, 1];
    ~0.55+ is a reasonable "same product" cutoff for short product titles.
    """
    from sentence_transformers import util

    results: dict = {p["sku"]: [] for p in my_products}
    if not my_products or not listings:
        return results

    model = _load_model(model_name)
    prod_emb = model.encode([p["name"] for p in my_products],
                            convert_to_tensor=True, normalize_embeddings=True)
    list_emb = model.encode([l.name for l in listings],
                            convert_to_tensor=True, normalize_embeddings=True)
    sim = util.cos_sim(prod_emb, list_emb)  # shape [P, L]

    for i, prod in enumerate(my_products):
        matches = [Match(listings[j], float(sim[i][j]))
                   for j in range(len(listings))
                   if float(sim[i][j]) >= threshold]
        matches.sort(key=lambda m: m.score, reverse=True)
        results[prod["sku"]] = matches
    return results
