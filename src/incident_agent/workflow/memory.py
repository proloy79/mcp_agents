from typing import Any, Dict, List, Tuple
import numpy as np
import logging
from logging_config import sep
from dataclasses import dataclass,asdict
import json

@dataclass
class MemoryText:
    text: str

KEYWORDS = {"spike", "error", "failure", "timeout", "latency"} #@TODO: to be removed when testing real scenarios
    
class Memory:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.entries: List[MemoryText] = []
        self.vocab = {}
    def _tokenize(self, text: str) -> List[str]:
        # Very small tokenizer: lowercase and split on whitespace/punct.
        import re
        
        toks = re.findall(r"[a-zA-Z0-9_]+", text.lower())
        return toks
    
    def _vectorize(self, text: str) -> np.ndarray:
        # Build/update vocabulary and return a normalized frequency vector.
        toks = self._tokenize(text)
        for t in toks:
            if t not in self.vocab:
                self.vocab[t] = len(self.vocab)
        vec = np.zeros(len(self.vocab), dtype=float)
        for t in toks:
            vec[self.vocab[t]] += 1.0
        # L2-normalize to turn dot product into cosine similarity.
        norm = np.linalg.norm(vec) or 1.0
        return vec / norm

    def add(self, text: str) -> None:
        # Append entry; update vocab lazily (vector created on demand).
        if any(entry.text == text for entry in self.entries):
            return  # skip duplicates
        self.entries.append(MemoryText(text))
    
    def _retrieve_topk(self, *, query: str, k: int = 1) -> List[Tuple[str, float]]:
        """
        Return top-k entries by cosine similarity to the query vector.
        - first convert the query into tokens so that the numbers can be compared across different vecs
        - compare the tokens using cosine similarity and get a comparison value between 0.0 and 1.0
        - sort all entries and return tok k
        """
        if not self.entries:
            return []
        #self.logger.debug(f"Memory: {self.entries}")
        # Warm the vocabulary with all entries so vectors have consistent length.
        for entry in self.entries:
            self.logger.debug(f"vectorize : {entry}")
            self._vectorize(entry.text)
        q = self._vectorize(query)
        scores: List[Tuple[str, float]] = []
        for e in self.entries:
            v = self._vectorize(e.text)
            score = float(np.dot(q, v))  # Cosine similarity in [0, 1].
            scores.append((e.text, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        
        return scores[:k]
        
    def _format_topk(self, topk: List[Tuple[str, float]]) -> str:
        if not topk:
            return "No relevant past incidents found."
    
        lines = []
        for i, (text, score) in enumerate(topk, start=1):
            score_pct = round(score * 100)
            lines.append(f"{i}. {text} ({score_pct}%)")
    
        return "\n".join(lines)
    
    def _summarize_last_n(self, *, n: int = 3, max_words: int = 20) -> str:
        """
        Take last n prompts,vectorize and keep the digits and capital words or words starting with capitals
        If none of these occur take the top max_wors count of most common words
        """
        self.logger.debug(self.entries)
        
        # Very small summary: take last n entries and keep key tokens.
        last = [e.text for e in self.entries[-n:]]
        joined = " ".join(last)
        toks = self._tokenize(joined)
        # Keep numbers and capitalized words from original fragments.
        keep: List[str] = []
        for frag in last:
            for w in frag.split():
                if (
                    w.isdigit()
                    or (w[:1].isupper() and w[1:].islower())
                    or w.isupper()
                    or w.lower() in KEYWORDS
                ):
                    keep.append(w)
        # Fallback to frequent tokens if keep is empty.
        if not keep:
            from collections import Counter

            counts = Counter(toks)
            keep = [w for w, _ in counts.most_common(max_words)]
        return " ".join(keep[:max_words])

    def _format_recent(self, last_n_summary: str) -> str:
        if not last_n_summary:
            return "No recent memory."
        return last_n_summary

    def build_memory_snippet(self, query: str, k: int = 3, n: int = 3) -> str:
        """
            Formats the memory snippet in a standard structure that holds past + recent details, if any
            ---
            Relevant past incidents:
            1. [summary] CPU spike on host A → python at 95% (88%)
            
            Recent activity:
            - [observation] CPU spike on host B
            - [diagnostic] host=B cpu_usage → high
            ---
        """
        topk = self._retrieve_topk(query=query, k=k)
        recent = self._summarize_last_n(n=n)
    
        formatted_topk = self._format_topk(topk)
        formatted_recent = self._format_recent(recent)
    
        snippet = (
            "Relevant past incidents:\n"
            f"{formatted_topk}\n\n"
            "Recent activity:\n"
            f"{formatted_recent}"
        )
        self.logger.info(f"Memory snippet for top_k={k} and last_={n}: \n{sep("-")}")
        self.logger.info(f"{snippet}\n{sep("-")}")
        
        return snippet
        
    def to_json(self) -> str:
        return json.dumps([asdict(e) for e in self.entries], indent=4, ensure_ascii=False)
