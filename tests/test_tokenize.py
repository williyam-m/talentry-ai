from talentry.nlp.tokenize import normalise, tokenize, char_ngrams


def test_normalise_keeps_techy_punctuation():
    assert normalise("Node.js + C++") == "node.js + c++"


def test_tokenize_drops_stopwords_and_collapses_synonyms():
    toks = tokenize("AI and ML engineer with NLP and LLMs")
    assert "and" not in toks
    assert toks.count("ai_ml") == 2
    assert "llm" in toks
    assert "nlp" in toks


def test_char_ngrams_short_input():
    assert list(char_ngrams("ab", n=3)) == ["ab"]
