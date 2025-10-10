import pandas as pd
import numpy as np
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from gensim import corpora, models
import spacy
from spacy.util import fix_random_seed
from keybert import KeyBERT
from langdetect import detect





def split_sentence(sentence, max_length=100):
    nlp = spacy.load('en_core_web_sm')
    
    if len(sentence) > max_length:
        # First, try splitting by ','
        if ', ' in sentence:
            parts = sentence.split(',')
            num_parts = len(parts)
            split_index = num_parts // 2

            # Find the optimal split index by minimizing the absolute difference in lengths
            optimal_split_index = split_index
            min_length_diff = abs(sum(len(part) for part in parts[:split_index]) - sum(len(part) for part in parts[split_index:]))
            for i in range(split_index + 1, num_parts):
                length_diff = abs(sum(len(part) for part in parts[:i]) - sum(len(part) for part in parts[i:]))
                if length_diff < min_length_diff:
                    optimal_split_index = i
                    min_length_diff = length_diff

            part1 = ','.join(parts[:optimal_split_index])
            part2 = ','.join(parts[optimal_split_index:])
                        
            return part1, part2
        
        # If ',' not found, proceed with original logic
        length = len(sentence) // 2
        split_index = sentence.rfind(" ", 0, int(length))

        if split_index != -1:
            part1 = sentence[:split_index].strip()
            part2 = sentence[split_index + 1:].strip()

            last_word_part1 = nlp(part1.split()[-1])
            if last_word_part1 and last_word_part1[0].pos_ == 'VERB':
                part1 = ' '.join(part1.split()[:-1]).strip()
                part2 = last_word_part1.text + ' ' + part2

                return part1, part2

        doc = nlp(sentence)
        for token in reversed(doc):
            if token.pos_ == 'VERB':
                split_index = token.idx
                part1 = sentence[:split_index].strip()
                part2 = sentence[split_index:].strip()
                return part1, part2

        part1 = sentence[:max_length].strip()
        part2 = sentence[max_length:].strip()
        return part1, part2
    else:
        return sentence, None


def preprocess_text(text):
    stop_words = set(stopwords.words('english'))
    sentences = sent_tokenize(text)
    tokenized_sentences = [nltk.word_tokenize(sentence.lower()) for sentence in sentences]
    filtered_sentences = [
        [word for word in sentence if word.isalnum() and word not in stop_words]
        for sentence in tokenized_sentences
    ]
    return sentences, filtered_sentences

def clean_terms(top_terms):
    nlp = spacy.load('en_core_web_sm')
    doc = nlp(' '.join(top_terms))
    cleaned_terms = [
        token.text
        for token in doc
        if token.pos_ in ['NOUN']
    ]
    return cleaned_terms

def extract_keywords(text):
    keybert = KeyBERT()
    keywords = keybert.extract_keywords(text, keyphrase_ngram_range=(1, 1), stop_words='english')
    return [keyword[0] for keyword in keywords]



def extract_noun_keywords(text, top_n=2):
    
    kw_model = KeyBERT()
    nlp = spacy.load("en_core_web_sm")
    keywords = kw_model.extract_keywords(text, keyphrase_ngram_range=(1, 1), stop_words='english', top_n=10)

    doc = nlp(text)
    nouns = [token.text for token in doc if token.pos_ == "NOUN"]

    noun_keywords = [keyword[0] for keyword in keywords if keyword[0] in nouns][:top_n]

    return noun_keywords

def find_topics(text):
    np.random.seed(42)

    sentences, filtered_sentences = preprocess_text(text)

    #dictionary = corpora.Dictionary(filtered_sentences)
    #corpus = [dictionary.doc2bow(sentence) for sentence in filtered_sentences]

    np.random.seed(42)

    #lda_model = models.LdaModel(corpus, num_topics=len(sentences), id2word=dictionary, passes=15, random_state=42)

    topic_data = []
    for sentence_id, sentence in enumerate(sentences):
        part1, part2 = split_sentence(sentence)
        original_sentence = sentence  # Store the original sentence before any splitting

        if part2:
            #topics_part1 = lda_model.get_document_topics(corpus[sentence_id])
            #topics_part2 = lda_model.get_document_topics(dictionary.doc2bow(part2.lower().split()))
            #combined_topics = topics_part1 + topics_part2

            #top_topic = max(combined_topics, key=lambda x: x[1])
            #top_terms = [term[0] for term in lda_model.show_topic(top_topic[0])]
            cleaned_terms = extract_noun_keywords(original_sentence)

            topic_data.append({'id': sentence_id + 1, 'original_sentence': original_sentence, 'sentence': part1, 'terms': cleaned_terms[:2]})
            topic_data.append({'id': sentence_id + 1, 'original_sentence': original_sentence, 'sentence': part2, 'terms': cleaned_terms[:2]})
        else:
            #topics = lda_model.get_document_topics(corpus[sentence_id])
            #top_topic = max(topics, key=lambda x: x[1])
            #top_terms = [term[0] for term in lda_model.show_topic(top_topic[0])]
            
            cleaned_terms = extract_noun_keywords(original_sentence)

            topic_data.append({'id': sentence_id + 1, 'original_sentence': original_sentence, 'sentence': sentence, 'terms': cleaned_terms[:2]})

    df = pd.DataFrame(topic_data)
    df['sentence_part_id'] = df.index

    return df





