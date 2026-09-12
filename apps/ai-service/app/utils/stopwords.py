from __future__ import annotations

import re

# Standard English stopwords (derived from NLTK / scikit-learn / Lucene standard stoplists)
STOPWORDS: frozenset[str] = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can't", "cannot", "could", "couldn't",
    "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down", "during",
    "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here",
    "here's", "hers", "herself", "him", "himself", "his", "how", "how's", "i",
    "i'd", "i'll", "i'm", "i've", "if", "in", "into", "is", "isn't", "it",
    "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same",
    "shan't", "she", "she'd", "she'll", "she's", "should", "shouldn't", "so",
    "some", "such", "than", "that", "that's", "the", "their", "theirs", "them",
    "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll",
    "they're", "they've", "this", "those", "through", "to", "too", "under", "until",
    "up", "very", "was", "wasn't", "we", "we'd", "we'll", "we're", "we've",
    "were", "weren't", "what", "what's", "when", "when's", "where", "where's",
    "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your",
    "yours", "yourself", "yourselves",
})


def remove_stopwords(text: str, preserve_case: bool = False) -> str:
    """
    Remove English stop words from a given text string.

    Tokens are extracted while preserving alpha-numeric characters and internal hyphens.
    If preserve_case is True, the original casing of non-stop words is preserved.
    """
    if not text or not text.strip():
        return ""

    tokens = text.split()
    kept: list[str] = []
    for token in tokens:
        # Strip outer punctuation for check
        clean_token = re.sub(r"^[^a-zA-Z0-9]+|[^a-zA-Z0-9]+$", "", token)
        if not clean_token:
            continue
        if clean_token.lower() in STOPWORDS:
            continue
        kept.append(token if preserve_case else clean_token.lower())

    return " ".join(kept).strip()


def filter_keyword(keyword: str) -> str:
    """
    Clean a search keyword phrase by removing stop words.
    If all words in the keyword were stop words, returns the trimmed original to avoid empty string.
    """
    cleaned = remove_stopwords(keyword, preserve_case=True)
    return cleaned if cleaned else keyword.strip()


def filter_keywords(keywords: list[str]) -> list[str]:
    """
    Clean, deduplicate, and remove stop words across a list of search keywords.
    """
    seen: set[str] = set()
    result: list[str] = []
    for raw in keywords:
        if not raw or not raw.strip():
            continue
        cleaned = filter_keyword(raw)
        norm = cleaned.lower()
        if norm and norm not in seen:
            seen.add(norm)
            result.append(cleaned)
    return result
