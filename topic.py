import pandas as pd
import ollama
from nltk.tokenize import sent_tokenize
import json


def split_sentence(sentence, max_length=100):
    """
    Split long sentences into two parts only at periods.
    If no period exists, keep sentence as one.
    """
    if len(sentence) <= max_length:
        return sentence, None
    
    # Try splitting by period only
    if '. ' in sentence:
        parts = sentence.split('. ')
        mid_point = len(parts) // 2
        
        # Find optimal split to balance lengths
        optimal_split = mid_point
        min_diff = float('inf')
        
        for i in range(1, len(parts)):
            left_len = len('. '.join(parts[:i]))
            right_len = len('. '.join(parts[i:]))
            diff = abs(left_len - right_len)
            
            if diff < min_diff:
                min_diff = diff
                optimal_split = i
        
        part1 = '. '.join(parts[:optimal_split]).strip()
        part2 = '. '.join(parts[optimal_split:]).strip()
        
        # Add period back to first part if it doesn't end with one
        if not part1.endswith('.'):
            part1 += '.'
            
        return part1, part2
    
    # No period found - keep as one sentence
    return sentence, None


def extract_noun_keywords(text, model='llama3.1', top_n=3):
    """
    Extract noun-based keywords using Ollama LLM.
    Returns format matching KeyBERT output: Title Case, proper nouns emphasized.
    
    Args:
        text: Input text to analyze
        model: Ollama model name (default: 'llama3.1')
        top_n: Number of keywords to extract (default: 2)
    
    Returns:
        List of keyword strings in Title Case format
    """
    prompt = f"""Extract exactly {top_n} main topics from this text.

STRICT RULES:
1. Extract ONLY the CORE subjects/themes discussed in the text
2. Topics must be CENTRAL to the text content, not peripheral mentions
3. Use NOUNS or NOUN PHRASES only (no verbs, adjectives, or generic words)
4. Prioritize:
   - Proper nouns (names, places, organizations)
   - Specific concepts or entities that are the FOCUS of the text
   - Technical terms or domain-specific vocabulary
5. EXCLUDE:
   - Generic words (thing, person, place, time, way)
   - Common verbs used as nouns (doing, making, thinking)
   - Words mentioned only once in passing
   - Overly broad categories
6. Use Title Case (capitalize first letter of each word)
7. Topics should be 1-4 words maximum
8. Return ONLY a valid JSON array, no explanation or additional text

Text: "{text}"

Required format: ["Topic One", "Topic Two", "Topic Three"]

JSON:"""

    try:
        response = ollama.generate(
            model=model,
            prompt=prompt,
            options={
                'temperature': 0.2,  # Low temperature for consistency
                'num_predict': 80,
            }
        )
        
        content = response['response'].strip()
        
        # Extract JSON array from response
        start_idx = content.find('[')
        end_idx = content.rfind(']') + 1
        
        if start_idx != -1 and end_idx > start_idx:
            json_str = content[start_idx:end_idx]
            keywords = json.loads(json_str)
            
            # Ensure Title Case format to match KeyBERT output
            formatted_keywords = []
            for kw in keywords[:top_n]:
                # Convert to Title Case
                formatted_kw = ' '.join(word.capitalize() for word in str(kw).split())
                formatted_keywords.append(formatted_kw)
            
            return formatted_keywords
        else:
            # Fallback parsing
            keywords = json.loads(content)
            formatted_keywords = []
            for kw in keywords[:top_n]:
                formatted_kw = ' '.join(word.capitalize() for word in str(kw).split())
                formatted_keywords.append(formatted_kw)
            return formatted_keywords[:top_n]
            
    except Exception as e:
        print(f"Error extracting keywords with LLM: {e}")
        print(f"LLM Response: {content if 'content' in locals() else 'No response'}")
        # Return empty list to match KeyBERT behavior on error
        return []


def find_topics(text, model='llama3.1'):
    """
    Process text and extract topics - OUTPUT MATCHES KEYBERT VERSION EXACTLY.
    
    Args:
        text: Input text to process
        model: Ollama model name (default: 'llama3.1')
    
    Returns:
        DataFrame with columns: ['id', 'original_sentence', 'sentence', 'terms', 'sentence_part_id']
    """
    # Tokenize into sentences
    sentences = sent_tokenize(text)
    
    topic_data = []
    
    for sentence_id, sentence in enumerate(sentences):
        part1, part2 = split_sentence(sentence)
        original_sentence = sentence  # Store the original sentence
        
        if part2:
            # Sentence was split - extract topics from ORIGINAL sentence
            cleaned_terms = extract_noun_keywords(original_sentence, model=model, top_n=2)
            
            # Add both parts with same terms (matching KeyBERT behavior)
            topic_data.append({
                'id': sentence_id + 1,
                'original_sentence': original_sentence,
                'sentence': part1,
                'terms': cleaned_terms[:2]
            })
            topic_data.append({
                'id': sentence_id + 1,
                'original_sentence': original_sentence,
                'sentence': part2,
                'terms': cleaned_terms[:2]
            })
        else:
            # Single part sentence
            cleaned_terms = extract_noun_keywords(original_sentence, model=model, top_n=2)
            
            topic_data.append({
                'id': sentence_id + 1,
                'original_sentence': original_sentence,
                'sentence': sentence,
                'terms': cleaned_terms[:2]
            })
    
    # Create DataFrame with exact same structure as KeyBERT version
    df = pd.DataFrame(topic_data)
    df['sentence_part_id'] = df.index
    
    return df


# Test to verify output matches
if __name__ == "__main__":
    # Test with the same text from your example
    test_text = "The journey of coffee begins in tropical regions around the world, where coffee plants thrive in the shade of mountainous terrain. Countries like Ethiopia, Colombia, Brazil, and Vietnam have built entire economies around this beloved crop. Each region imparts its own unique characteristics to the beans, influenced by altitude, soil composition, and climate. Ethiopian coffee often carries floral and fruity notes, while Colombian beans are known for their smooth, balanced flavor."
    
    print("Testing Ollama LLM version:")
    print("="*50)
    
    df = find_topics(test_text)
    print(df)
    
    print("\n" + "="*50)
    print("Expected output format (like KeyBERT):")
    print("="*50)
    print("""
   id                                  original_sentence  ...                                     terms sentence_part_id
0   1  Quantum computing represents a groundbreaking ...  ...  [Quantum Computing, Classical Computers]                0
1   1  Quantum computing represents a groundbreaking ...  ...  [Quantum Computing, Classical Computers]                1
    """)