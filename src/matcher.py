from src.data_loader import DataLoader
from src.llm_service import LLMService
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import os
import time


class SmartMatcher:
    def __init__(self):
        self.data_loader = DataLoader()
        self.llm = LLMService()

        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=384)
        self.skill_vectorizer = TfidfVectorizer(analyzer='char_wb', ngram_range=(3, 5), max_features=4096)

        self.candidates_cache = []
        self._initialized = False
        self._text_matrix = None
        self._skill_matrix = None
        self.current_role = None
        self.last_error = None
        self.last_progress: list[str] = []
        self.current_percent = 0
        self.current_status = "Idle"

        self.top_k = int(os.getenv("TOP_K_RESULTS", "100"))
        self.stage1_limit = int(os.getenv("STAGE1_LIMIT", "20"))
        self.stage2_limit = int(os.getenv("STAGE2_LIMIT", "5"))
        self.stage2_weight = float(os.getenv("STAGE2_WEIGHT", "0.4"))
        self.stage2_max_seconds = float(os.getenv("STAGE2_MAX_SECONDS", "8"))

    def _log(self, message: str):
        msg = str(message).strip()
        if not msg:
            return
        self.last_progress.append(msg)
        print(msg)

    def _set_progress(self, percent: float, status: str):
        self.current_percent = int(max(0, min(100, percent)))
        self.current_status = status
        self._log(status)

    def _chunk_text(self, text, chunk_word_count=80, overlap_word_count=40, max_chunks=50):
        if not isinstance(text, str):
            return []
        tokens = text.split()
        if not tokens:
            return []
        if len(tokens) <= chunk_word_count:
            return [" ".join(tokens)]
        step = max(1, chunk_word_count - overlap_word_count)
        chunks = []
        for start in range(0, len(tokens), step):
            end = start + chunk_word_count
            chunk_tokens = tokens[start:end]
            if not chunk_tokens:
                break
            chunks.append(" ".join(chunk_tokens))
            if end >= len(tokens) or len(chunks) >= max_chunks:
                break
        return chunks

    def _tokenize_lower(self, text: str):
        if not isinstance(text, str):
            return []
        tokens = []
        for t in text.replace('/', ' ').replace(',', ' ').replace(';', ' ').split():
            t = t.strip().lower()
            if t:
                tokens.append(t)
        return tokens

    def _ensure_initialized(self, position_filter=None):
        if self._initialized and position_filter == self.current_role:
            return True
        try:
            self.last_progress = []
            self._log("Loading candidates...")
            self.candidates_cache = self.data_loader.load_candidates(position_filter=position_filter)
            docs = [c.get("Long Description", "") for c in self.candidates_cache]
            skill_docs = [" ".join(c.get("skill_hints", [])) for c in self.candidates_cache]

            if docs:
                self.vectorizer.fit(docs)
                self._text_matrix = self.vectorizer.transform(docs)
            if skill_docs:
                self.skill_vectorizer.fit(skill_docs)
                self._skill_matrix = self.skill_vectorizer.transform(skill_docs)

            self.current_role = position_filter
            self._initialized = True
            self._log(f"Initialized {len(self.candidates_cache)} candidates (max {self.data_loader.max_candidates}).")
            return True
        except Exception as e:
            self.last_error = str(e)
            self._log(f"Initialization failed: {e}")
            return False

    def _parse_float(self, value, default=0.0):
        try:
            return float(str(value).replace('y', '').strip())
        except Exception:
            return default

    def _stage1_score(self, cand, jd_analysis, jd_vec, jd_skill_vec, idx):
        hard_reqs = jd_analysis.get('hard_requirements', {}) or {}
        role_keywords = jd_analysis.get('role_keywords', []) or []
        req_skills = hard_reqs.get('required_skills', []) or []

        cand_text_vec = self._text_matrix[idx] if self._text_matrix is not None else None
        cand_skill_vec = self._skill_matrix[idx] if self._skill_matrix is not None else None

        soft_sim = 0.0
        if jd_vec is not None and cand_text_vec is not None:
            soft_sim = float(cosine_similarity(jd_vec, cand_text_vec)[0][0])

        skill_sim = 0.0
        if jd_skill_vec is not None and cand_skill_vec is not None:
            skill_sim = float(cosine_similarity(jd_skill_vec, cand_skill_vec)[0][0])

        lf_tokens = self._tokenize_lower(cand.get('looking_for_text', ''))
        jd_kw_tokens = [k.strip().lower() for k in role_keywords if isinstance(k, str)]
        lf_overlap = 0.0
        if jd_kw_tokens and lf_tokens:
            inter = len(set(jd_kw_tokens) & set(lf_tokens))
            lf_overlap = inter / max(1, len(set(jd_kw_tokens)))

        min_years = hard_reqs.get('min_experience_years', 0) or 0
        exp_years = self._parse_float(cand.get('Experience Years', cand.get('Exp Years', 0)), 0.0)
        exp_score = 1.0 if exp_years >= min_years else exp_years / max(1.0, float(min_years) or 1.0)

        req_english = hard_reqs.get('english_level', None)
        eng_score = 1.0 if not req_english else (1.0 if LLMService.english_level_satisfies(cand.get("English Level"), req_english) else 0.0)

        stage1 = 0.35 * skill_sim + 0.35 * soft_sim + 0.15 * lf_overlap + 0.1 * exp_score + 0.05 * eng_score
        return max(0.0, min(stage1, 1.0)), {
            'soft_sim': soft_sim,
            'skill_sim': skill_sim,
            'lf_overlap': lf_overlap,
            'exp_score': exp_score,
            'eng_score': eng_score,
            'exp_years': exp_years,
            'min_years': min_years,
            'role_keywords': jd_kw_tokens,
            'req_skills': req_skills,
        }

    def match(self, query_text: str, position_filter=None, target_role=None):
        self.last_error = None
        self.last_progress = []
        self._set_progress(0, "Initializing...")

        # Accept legacy caller argument name
        if target_role is not None and position_filter is None:
            position_filter = target_role

        if not isinstance(query_text, str) or not query_text.strip():
            self.last_error = "Job description is empty"
            self._set_progress(0, "Job description is empty")
            return []

        if not self._ensure_initialized(position_filter=position_filter):
            self._set_progress(0, "Initialization failed")
            return []

        self._set_progress(10, "Step 1: Analyzing JD intent and requirements via LLM...")
        jd_analysis = self.llm.analyze_jd(query_text) or {"role_keywords": [], "hard_requirements": {}, "soft_requirements": {}, "role_title": None}
        hard_reqs = jd_analysis.get('hard_requirements', {}) or {}
        role_keywords = jd_analysis.get('role_keywords', []) or []
        req_skills = hard_reqs.get('required_skills', []) or []

        jd_vec = None
        jd_skill_vec = None
        try:
            if self.vectorizer.vocabulary_:
                jd_vec = self.vectorizer.transform([query_text])
            skill_text = " ".join([*role_keywords, *req_skills])
            if self.skill_vectorizer.vocabulary_ and skill_text.strip():
                jd_skill_vec = self.skill_vectorizer.transform([skill_text])
        except Exception as e:
            self._log(f"Vectorization warning: {e}")

        scored_candidates = []
        self._set_progress(25, f"Step 2: Stage-1 scoring over {len(self.candidates_cache)} candidates (intent + skills)...")
        stage1_count = max(1, len(self.candidates_cache))
        for idx, cand in enumerate(self.candidates_cache):
            stage1_score, detail = self._stage1_score(cand, jd_analysis, jd_vec, jd_skill_vec, idx)
            scored_candidates.append({
                "id": cand.get('id'),
                "name": cand.get('Name') or cand.get('id', 'Unknown'),
                "position": cand.get('Position'),
                "english_level": cand.get("English Level"),
                "skills": cand.get('skill_hints', []),
                "total_score": round(stage1_score * 100, 1),
                "hard_pass_rate": round(detail['exp_score'] * 100, 0),
                "soft_score": round(detail['soft_sim'], 3),
                "tags": [f"{int(detail['min_years'])}+ Years"] if detail['min_years'] else [],
                "raw_exp_years": detail['exp_years'],
                "_stage1": stage1_score,
                "_cand_ref": cand,
                "_detail": detail,
            })
            # Smooth progress up to 60%
            prog = 25 + int((idx + 1) / stage1_count * 35)
            self._set_progress(prog, f"Stage-1 scoring {idx+1}/{stage1_count}")

        scored_candidates.sort(key=lambda c: c['_stage1'], reverse=True)
        stage1_top = scored_candidates[: self.stage1_limit]
        self._set_progress(60, f"Stage-1 complete. Kept top {len(stage1_top)} for deep rerank.")

        # Stage-2 LLM deep evaluation on top-N
        final_results = []
        use_stage2 = bool(self.llm.api_key)
        if use_stage2:
            self._set_progress(65, f"Step 3: Stage-2 LLM rerank on top {min(len(stage1_top), self.stage2_limit)} candidates...")
            stage2_start = time.time()
            stage2_total = max(1, min(len(stage1_top), self.stage2_limit))
            for idx, c in enumerate(stage1_top[: self.stage2_limit]):
                if time.time() - stage2_start > self.stage2_max_seconds:
                    self._set_progress(95, "Stage-2 stopped early due to time budget; returning partial results.")
                    break
                cand = c.pop('_cand_ref', {})
                cand_summary = cand.get('Long Description', '')
                self._set_progress(65 + int((idx + 1) / stage2_total * 30), f"LLM evaluating candidate {c.get('id')} ({idx+1}/{stage2_total})...")
                llm_score_obj = self.llm.score_candidate_for_jd(query_text, cand_summary)
                fit_score = 0.0
                strengths = []
                risks = []
                verdict = ""
                if isinstance(llm_score_obj, dict):
                    try:
                        fit_score = float(llm_score_obj.get('fit_score', 0) or 0)
                    except Exception:
                        fit_score = 0.0
                    strengths = llm_score_obj.get('strengths') or []
                    risks = llm_score_obj.get('risks') or []
                    verdict = llm_score_obj.get('verdict') or ''
                combined = (1 - self.stage2_weight) * (c.get('_stage1', 0)) * 100 + self.stage2_weight * fit_score
                c['total_score'] = round(combined, 1)
                c['llm_fit_score'] = round(fit_score, 1)
                c['llm_strengths'] = strengths
                c['llm_risks'] = risks
                c['llm_verdict'] = verdict
                final_results.append(c)
        else:
            self._log("Stage-2 skipped: LLM API key missing. Returning Stage-1 scores only.")
            for c in stage1_top:
                c.pop('_cand_ref', None)
                c['llm_fit_score'] = None
                final_results.append(c)

        # Append remaining Stage-1 results (without LLM) if we still need more up to top_k
        if len(final_results) < self.top_k:
            for c in stage1_top[self.stage2_limit: self.top_k]:
                c.pop('_cand_ref', None)
                c['llm_fit_score'] = None
                final_results.append(c)

        final_results.sort(key=lambda c: c['total_score'], reverse=True)
        final_results = final_results[: self.top_k]
        self._set_progress(100, f"Stage-2 complete. Returning top {len(final_results)} candidates.")

        return final_results