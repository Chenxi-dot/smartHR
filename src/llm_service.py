import json
import os
from typing import Any, Dict, Optional
from openai import OpenAI

# Qwen API config (env overrides)
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "ms-60c5577d-33b4-401f-ac7f-2479fdf4dfd5")
QWEN_BASE_URL = os.getenv("QWEN_BASE_URL", "https://api-inference.modelscope.cn/v1/")
QWEN_MODEL = os.getenv("QWEN_MODEL", "Qwen/Qwen2.5-7B-Instruct")
# Keep the LLM call fast to avoid worker timeouts; override via QWEN_TIMEOUT if needed
LLM_TIMEOUT = float(os.getenv("QWEN_TIMEOUT", "8"))  # seconds (read timeout)

class LLMService:
    ENGLISH_LEVELS = ("basic", "pre", "intermediate", "upper", "fluent")
    _ENGLISH_LEVEL_RANK = {
        "basic": 1,
        "pre": 2,
        "intermediate": 3,
        "upper": 4,
        "fluent": 5,
    }

    def __init__(self):
        # Use Qwen model on DashScope
        self.model = QWEN_MODEL
        self.api_key = QWEN_API_KEY
        self.client = OpenAI(api_key=self.api_key, base_url=QWEN_BASE_URL)

    @classmethod
    def normalize_english_level(cls, value: Any) -> Optional[str]:
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip().lower()
            if not s:
                return None
            if s in cls.ENGLISH_LEVELS:
                return s
            if s in ("no_english", "none", "n/a", "na", "unknown"):
                return "basic"
            if "fluent" in s or "native" in s or "c2" in s:
                return "fluent"
            if "upper" in s or "advanced" in s or "b2" in s:
                return "upper"
            if "intermediate" in s or "b1" in s:
                return "intermediate"
            if s == "pre-intermediate" or "pre" in s or "a2" in s:
                return "pre"
            if "basic" in s or "a1" in s:
                return "basic"
            return None
        return None

    @classmethod
    def english_level_rank(cls, level: Any) -> int:
        normalized = cls.normalize_english_level(level)
        if not normalized:
            return 0
        return int(cls._ENGLISH_LEVEL_RANK.get(normalized, 0))

    @classmethod
    def english_level_satisfies(cls, candidate_level: Any, required_level: Any) -> bool:
        req = cls.normalize_english_level(required_level)
        if not req:
            return True
        return cls.english_level_rank(candidate_level) >= cls.english_level_rank(req)

    def parse_resume(self, resume_text):
        """
        Parses unstructured resume text into structured JSON.
        """
        if not isinstance(resume_text, str):
            resume_text = str(resume_text)
        if not self.api_key:
            print("LLM skipped: API_KEY not configured")
            return None
        prompt = f"""
You are an expert HR assistant. Extract structured information from a candidate profile.
The input may include labeled sections such as Position, Primary Keyword, English Level, Experience Years, Looking For, Highlights, Moreinfo, and CV.
Output MUST be valid JSON only (no markdown, no comments).

Extraction rules:
- Only extract information that is explicitly supported by the input text.
- If a field is unknown, use null (for scalars/objects) or [] (for arrays).
- Normalize tech skills into short phrases (e.g., \"Apache Spark\", \"Airflow\", \"AWS S3\", \"SQL\", \"Python\").
- Keep lists deduplicated and reasonably sized.

Candidate Profile Text:
{resume_text[:4000]}

Required JSON Structure:
{{
  "schema_version": 2,
  "name": "Full Name (standardized) or null",
  "contact": {{
    "phone": "verified phone or null",
    "email": "verified email or null"
  }},
  "profile": {{
    "headline_position": "string or null",
    "primary_keyword": "string or null",
    "english_level": "string or null",
    "experience_years": "number or null",
    "seniority": "junior|mid|senior|lead|principal|unknown"
  }},
  "looking_for": {{
    "target_roles": ["Role 1", "Role 2"],
    "target_locations": ["Location 1"],
    "salary": {{"min": "number or null", "max": "number or null", "currency": "string or null", "period": "month|year|hour|unknown"}},
    "work_mode": "remote|hybrid|onsite|unknown",
    "other_preferences": ["string"]
  }},
  "highlights": ["string"],
  "education": [
    {{
      "school": "string or null",
      "major": "string or null",
      "degree": "Bachelor|Master|PhD|Associate|Bootcamp|Other|Unknown",
      "start_date": "YYYY-MM or null",
      "end_date": "YYYY-MM or null"
    }}
  ],
  "work_experience": [
    {{
      "company": "string or null",
      "position": "string or null",
      "period": "YYYY-MM to YYYY-MM or null",
      "responsibilities": ["string"],
      "tech_stack": ["string"]
    }}
  ],
  "projects": [
    {{
      "name": "string or null",
      "summary": "string or null",
      "tech_stack": ["string"]
    }}
  ],
  "skills_certs": {{
    "certifications": [{{"name": "string", "level": "string or null", "expiry": "string or null"}}],
    "languages": ["string"],
    "tech_skills": ["string"]
  }},
  "english_level": "string or null"
}}
"""
        parsed = self._call_llm(prompt)
        return self._postprocess_parsed_resume(parsed)

    def analyze_jd(self, jd_text):
        """
        Extract role intent, keywords, and hard/soft requirements from JD.
        """
        if not isinstance(jd_text, str):
            jd_text = str(jd_text)
        if not self.api_key:
            print("LLM skipped: API_KEY not configured")
            return None
        prompt = f"""
You are an HR analyst. Given a Job Description, identify the role intent and extract concise requirements.
Return ONLY JSON with fields: role_title (string), role_keywords (3-8 strings), hard_requirements, soft_requirements.
Rules: keep skills as short phrases; unknown values use null or [] ; english_level in [basic, pre, intermediate, upper, fluent] or null.

Job Description:
{jd_text}

Required JSON schema:
{{
  "role_title": "string or null",
  "role_keywords": ["kw1", "kw2"],
  "hard_requirements": {{
      "min_experience_years": 0,
      "required_skills": ["skill1", "skill2"],
      "education": "string or null",
      "english_level": "basic|pre|intermediate|upper|fluent or null"
  }},
  "soft_requirements": {{
      "traits": ["trait1", "trait2"],
      "preferred": ["pref1"]
  }}
}}
"""
        analysis = self._call_llm(prompt)
        return self._postprocess_jd_analysis(analysis)

    def score_candidate_for_jd(self, jd_text, candidate_summary):
        """Deep evaluation for a candidate vs JD; returns dict with fit_score and rationale."""
        if not self.api_key:
            print("LLM skipped: API_KEY not configured")
            return None
        prompt = f"""
You are a hiring evaluator. Given a JD and a candidate profile, provide a holistic fit score 0-100 and rationale.
Keep JSON only, concise rationale.

Job Description:
{jd_text}

Candidate Profile:
{candidate_summary}

Respond JSON:
{{
  "fit_score": 78,
  "strengths": [""],
  "risks": [""],
  "verdict": "short sentence"
}}
"""
        return self._call_llm(prompt)

    def _call_llm(self, prompt):
        if not self.api_key:
            print("LLM call aborted: missing API_KEY")
            return None
        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                stream=False,
                timeout=LLM_TIMEOUT,
            )
            content = resp.choices[0].message.content
            if not content:
                return None
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except Exception as e:
            print(f"LLM Exception: {e}")
            return None

    def _postprocess_parsed_resume(self, parsed: Any) -> Dict[str, Any]:
        if not isinstance(parsed, dict):
            parsed = {}

        top_level = self.normalize_english_level(parsed.get("english_level"))
        if top_level is not None:
            parsed["english_level"] = top_level

        profile = parsed.get("profile")
        if isinstance(profile, dict):
            profile_level = self.normalize_english_level(profile.get("english_level"))
            if profile_level is not None:
                profile["english_level"] = profile_level
            parsed["profile"] = profile

        return parsed

    def _postprocess_jd_analysis(self, analysis: Any) -> Dict[str, Any]:
        if not isinstance(analysis, dict):
            return {"role_keywords": [], "role_title": None, "hard_requirements": {}, "soft_requirements": {}}

        hard = analysis.get("hard_requirements")
        if not isinstance(hard, dict):
            hard = {}
        english_level = self.normalize_english_level(hard.get("english_level"))
        hard["english_level"] = english_level
        analysis["hard_requirements"] = hard

        soft = analysis.get("soft_requirements")
        if not isinstance(soft, dict):
            soft = {}
        analysis["soft_requirements"] = soft

        role_keywords = analysis.get("role_keywords")
        if not isinstance(role_keywords, list):
            role_keywords = []
        analysis["role_keywords"] = [k for k in role_keywords if isinstance(k, str) and k.strip()]
        if "role_title" not in analysis:
            analysis["role_title"] = None

        return analysis
