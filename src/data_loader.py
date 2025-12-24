import os
import sys
import pandas as pd

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from src.cache_manager import CacheManager
from src.llm_service import LLMService

class DataLoader:
    def __init__(self, data_path="candidates.parquet"):
        if isinstance(data_path, str) and not os.path.isabs(data_path):
            data_path = os.path.join(_PROJECT_ROOT, data_path)
        self.data_path = data_path
        self.cache = CacheManager(db_path=os.path.join(_PROJECT_ROOT, "parsed_data.db"))
        self.llm = LLMService()
        self.max_candidates = int(os.getenv("MAX_CANDIDATES", "50000"))
        self._all_candidates = None  # cached in-memory dataset

    def _to_str(self, v):
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        return str(v)

    def _build_long_description(self, cand):
        """Lightweight textual summary for ranking/LLM prompts."""
        parts = []
        position = self._to_str(cand.get("Position", "")).strip()
        primary_keyword = self._to_str(cand.get("Primary Keyword", "")).strip()
        english_level = LLMService.normalize_english_level(cand.get("English Level", "")) or self._to_str(cand.get("English Level", "")).strip()
        exp_years = cand.get("Experience Years", "")
        looking_for = self._to_str(cand.get("Looking For", "")).strip()
        highlights = self._to_str(cand.get("Highlights", "")).strip()
        moreinfo = self._to_str(cand.get("Moreinfo", "")).strip()
        cv = self._to_str(cand.get("CV", "")).strip()

        if position:
            parts.append(f"Position: {position}")
        if primary_keyword:
            parts.append(f"Primary Keyword: {primary_keyword}")
        if english_level:
            parts.append(f"English Level: {english_level}")
        if exp_years != "" and exp_years is not None:
            parts.append(f"Experience Years: {exp_years}")
        if looking_for:
            parts.append(f"Looking For: {looking_for}")
        if highlights:
            parts.append(f"Highlights: {highlights}")
        if moreinfo:
            parts.append(f"Moreinfo: {moreinfo}")
        if cv:
            parts.append(f"CV: {cv}")

        return "\n".join(parts).strip()

    def _extract_candidate_skills(self, cand):
        """Extract raw skill hints from multiple fields (no LLM)."""
        fields = [
            cand.get("Primary Keyword", ""),
            cand.get("Highlights", ""),
            cand.get("Moreinfo", ""),
            cand.get("CV", ""),
        ]
        tokens = []
        for f in fields:
            if not isinstance(f, str):
                continue
            for t in f.replace("/", ",").replace(";", ",").split(','):
                t = t.strip()
                if t:
                    tokens.append(t)
        return tokens

    def _normalize_structured(self, structured_data, cand):
        """Kept for compatibility; now we mostly rely on raw fields for Stage-1 scoring."""
        if not isinstance(structured_data, dict):
            structured_data = {}
        return structured_data

    def _ensure_loaded(self):
        """Load and preprocess the full dataset once into memory."""
        if self._all_candidates is not None:
            return
        if not os.path.exists(self.data_path):
            print(f"Data file not found at {self.data_path}")
            self._all_candidates = []
            return
        try:
            df = pd.read_parquet(self.data_path)
            df = df.fillna("")
            df = df.head(self.max_candidates)
            raw_candidates = df.to_dict('records')
            processed_candidates = []
            print(f"Loading and processing {len(raw_candidates)} candidates into memory (no per-candidate LLM)...")
            for cand in raw_candidates:
                cand["English Level"] = LLMService.normalize_english_level(cand.get("English Level", "")) or "basic"
                cand["Long Description"] = self._build_long_description(cand)
                cand["skill_hints"] = self._extract_candidate_skills(cand)
                cand["looking_for_text"] = self._to_str(cand.get("Looking For", "")).strip()
                processed_candidates.append(cand)
            self._all_candidates = processed_candidates
        except Exception as e:
            print(f"Error loading data: {e}")
            self._all_candidates = []

    def load_candidates(self, position_filter=None):
        """
        Returns cached candidates; optional position filter is applied in-memory.
        """
        self._ensure_loaded()
        cands = self._all_candidates or []
        if position_filter:
            pf = position_filter.lower()
            cands = [c for c in cands if pf in self._to_str(c.get("Position", "")).lower()]
        return cands

if __name__ == "__main__":
    loader = DataLoader()
    candidates = loader.load_candidates()
    print(f"Loaded {len(candidates)} candidates.")
