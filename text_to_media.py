from nltk.tokenize import word_tokenize
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import CountVectorizer
from topic import find_topics
from collections import Counter
from nltk.corpus import wordnet
from nltk.corpus import stopwords
import nltk
from nltk.stem import WordNetLemmatizer
import ast

lemmatizer = WordNetLemmatizer()

def lemmatize_words(words):
    return [lemmatizer.lemmatize(word) for word in words]

def preprocess_text(text):
    stop_words = set(stopwords.words('english'))
    word_tokens = word_tokenize(text.lower())
    filtered_words = [w for w in word_tokens if w.isalnum() and w not in stop_words]
    return ' '.join(filtered_words)

def common_word_frequency(row, topics):
    keywords = row['keywords']
    count_topics = Counter(topics.split())
    count_keywords = Counter(keywords.split())
    common_words = set(count_topics.keys()) & set(count_keywords.keys())
    common_frequencies = {word: min(count_topics[word], count_keywords[word]) for word in common_words}
    return max(common_frequencies.values(), default=0)

def find_common_word(topics, keywords):
    topic_set = set(topics)
    keyword_set = set(keywords)
    common_words = topic_set.intersection(keyword_set)
    return len(common_words) > 0

def find_media_best(topics, processed_media_paths, metadata, l=1):
    metadata = metadata[~metadata['path_datalake'].isin(processed_media_paths)]
    


    topics = lemmatize_words(topics)
    print("Lemmatized topics:", topics)

    preprocessed_topics = preprocess_text(' '.join(topics))
    print("Preprocessed topics:", preprocessed_topics)

    metadata['preprocessed_keywords'] = metadata['new_description_keywords'].apply(lambda words: ' '.join(words))

    metadata['has_common_word'] = metadata['preprocessed_keywords'].apply(lambda x: find_common_word(topics, x.split()))

    filtered_metadata = metadata[metadata['has_common_word']]

    if not filtered_metadata.empty:
        filtered_metadata['max_common_frequency'] = filtered_metadata.apply(lambda row: common_word_frequency(row, preprocessed_topics), axis=1)

        highest_frequency = filtered_metadata['max_common_frequency'].max()

        rows_with_highest_frequency = filtered_metadata[filtered_metadata['max_common_frequency'] == highest_frequency].head(l)

        if not rows_with_highest_frequency.empty:
            topic_found = True
            media_found = True
            print(rows_with_highest_frequency["path_datalake"].tolist())
            return topic_found, media_found, rows_with_highest_frequency["path_datalake"].tolist()

    topic_found = False
    media_found = False
    return topic_found, media_found, []


# from nltk.tokenize import word_tokenize
# from sklearn.metrics.pairwise import cosine_similarity
# from sklearn.feature_extraction.text import CountVectorizer
# from topic import find_topics
# from collections import Counter
# from nltk.corpus import wordnet
# from nltk.corpus import stopwords

# def preprocess_text(text):
#     stop_words = set(stopwords.words('english'))
#     word_tokens = word_tokenize(text.lower())
#     filtered_words = [w for w in word_tokens if w.isalnum() and w not in stop_words]
#     return ' '.join(filtered_words)

# def calculate_similarity(topics, keywords):
#     vectorizer = CountVectorizer().fit_transform([topics, keywords])
#     vectors = vectorizer.toarray()
#     cosine_sim = cosine_similarity(vectors)
#     return cosine_sim[0][1]

# def common_word_frequency(row, topics):
#     keywords = row['keywords']
#     count_topics = Counter(topics.split())
#     count_keywords = Counter(keywords.split())
#     common_words = set(count_topics.keys()) & set(count_keywords.keys())
#     common_frequencies = {word: min(count_topics[word], count_keywords[word]) for word in common_words}
#     return max(common_frequencies.values(), default=0)

# def find_media_best(topics,processed_media_paths,metadata,l=1):
    
#     metadata = metadata[~metadata['path_datalake'].isin(processed_media_paths)]
#     topic_found=False
#     media_found=False

#     preprocessed_topics = preprocess_text(' '.join(topics))
    
#     metadata['preprocessed_keywords'] = metadata['keywords'].apply(lambda x: preprocess_text(' '.join(eval(x))))

#     metadata['similarity'] = metadata['preprocessed_keywords'].apply(lambda x: calculate_similarity(preprocessed_topics, x))

#     best_image_metadata = metadata.nlargest(100, 'similarity')

#     best_image_metadata['max_common_frequency'] = best_image_metadata.apply(lambda row: common_word_frequency(row, preprocessed_topics), axis=1)

#     highest_frequency = best_image_metadata['max_common_frequency'].max()

#     rows_with_highest_frequency = best_image_metadata[best_image_metadata['max_common_frequency'] == highest_frequency].head(l)
#     if not rows_with_highest_frequency.empty:
#         topic_found=True
#         media_found=True
#         return topic_found, media_found,rows_with_highest_frequency["path_datalake"].tolist()
#     else:
#         return topic_found, media_found,[]
    

