import re
import json
import random
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

class Metadata:
    def __init__(self, name="Unknown", email="", skills=None, exp_years=0, edu_level="Bachelor", expect_salary=0, work_location="Unknown", english_level="Intermediate"):
        self.name = name
        self.email = email
        self.skills = skills if skills else []
        self.exp_years = exp_years
        self.edu_level = edu_level
        self.expect_salary = expect_salary
        self.work_location = work_location
        self.english_level = english_level

    def to_dict(self):
        return {
            "name": self.name,
            "email": self.email,
            "skills": self.skills,
            "exp_years": self.exp_years,
            "edu_level": self.edu_level,
            "expect_salary": self.expect_salary,
            "work_location": self.work_location,
            "english_level": self.english_level
        }

class LLMProcessor:
    def __init__(self):
        """
        Initializes the processor.
        NOTE: In a production environment with an API key, this would initialize the OpenAI/Anthropic client.
        For this local demo, we use:
        1. TfidfVectorizer for Real Vectorization (instead of LLM Embeddings).
        2. Regex/Heuristics for Metadata Extraction (instead of LLM Generation).
        """
        self.vectorizer = TfidfVectorizer(stop_words='english', max_features=384)
        self.is_fitted = False

    def fit_vectorizer(self, corpus):
        """
        Fits the TF-IDF vectorizer on the candidate descriptions.
        This ensures our 'embeddings' are mathematically grounded in the actual text content.
        """
        if not corpus:
            return
        self.vectorizer.fit(corpus)
        self.is_fitted = True
        print("TF-IDF Vectorizer fitted on corpus.")

    def get_embedding(self, text):
        """
        Generates a vector embedding for the text.
        """
        if not self.is_fitted:
            # Fallback if not fitted (should not happen if initialized correctly)
            # Use a dummy fit on the single text to avoid crash
            self.vectorizer.fit([text])
            self.is_fitted = True
            
        # Transform returns a sparse matrix, convert to dense array
        vector = self.vectorizer.transform([text]).toarray()[0]
        return vector.tolist()

    def extract_metadata(self, candidate_record):
        """
        Extracts structured metadata from a candidate record (dict).
        
        [SYSTEM NOTE]: To upgrade to Real LLM extraction:
        1. Replace the code below with a call to OpenAI API (e.g., chat.completions.create).
        2. Pass the 'Long Description' in the prompt.
        3. Request JSON output matching the Metadata structure.
        """
        # 1. Parse Experience Years
        raw_exp = str(candidate_record.get('Exp Years', '0'))
        exp_years = 0
        match = re.search(r'(\d+)', raw_exp)
        if match:
            exp_years = int(match.group(1))

        # 2. Parse English Level
        raw_eng = str(candidate_record.get('English Level', 'Intermediate')).lower()
        english_level = "Intermediate"
        if "advanced" in raw_eng or "fluent" in raw_eng or "upper" in raw_eng:
            english_level = "Advanced"
        elif "beginner" in raw_eng or "elementary" in raw_eng:
            english_level = "Beginner"

        # 3. Parse Skills (from Primary Keyword and Description)
        skills = []
        primary = candidate_record.get('Primary Keyword', '')
        if primary:
            skills.append(primary)
        
        desc = candidate_record.get('Long Description', '')
        # Simple keyword extraction for 2D Artist context
        keywords = ['Unity', 'Photoshop', 'Spine', 'UI', 'UX', 'Animation', 'Illustration', 'Concept Art']
        for k in keywords:
            if k.lower() in desc.lower() and k not in skills:
                skills.append(k)

        return Metadata(
            name=f"Candidate_{candidate_record.get('id', '0')[:5]}",
            email="candidate@example.com",
            skills=skills,
            exp_years=exp_years,
            edu_level="Bachelor", # Default assumption
            expect_salary=20000, # Default assumption
            work_location="Remote" if "remote" in desc.lower() else "Office",
            english_level=english_level
        )

    def parse_query(self, query):
        """
        Parses HR natural language query into structured criteria.
        
        [SYSTEM NOTE]: To upgrade to Real LLM parsing:
        1. Send 'query' to LLM.
        2. Prompt for JSON extraction of skills, min_exp, location.
        """
        criteria = {
            "skills": [],
            "min_exp": 0,
            "location": None
        }
        
        # Simple keyword extraction
        if "unity" in query.lower():
            criteria["skills"].append("Unity")
        if "photoshop" in query.lower():
            criteria["skills"].append("Photoshop")
            
        # Extract years
        year_match = re.search(r'(\d+)\s*(?:year|yr)', query.lower())
        if year_match:
            criteria["min_exp"] = int(year_match.group(1))
            
        return criteria
