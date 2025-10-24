import pandas as pd
import ollama
from nltk.tokenize import sent_tokenize
import json
import time


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


def extract_topics_from_sentence(sentence, model='llama3.1', top_n=2, retry_count=3):
    """
    Extract main topics from a single sentence using Ollama LLM.
    
    Args:
        sentence: Input sentence to analyze
        model: Ollama model name (default: 'llama3.1')
        top_n: Number of topics to extract (default: 2)
        retry_count: Number of retries on failure (default: 3)
    
    Returns:
        List of topic strings in Title Case format
    """
    # Improved prompt with clearer instructions
    prompt = f"""Analyze this sentence and extract exactly {top_n} main topics.

RULES:
1. Topics must be the MAIN subjects discussed in this specific sentence
2. Use NOUNS or NOUN PHRASES only (no verbs or adjectives)
3. Prioritize:
   - Proper nouns (names, places, organizations, brands)
   - Specific entities or concepts that are central to the sentence
   - Technical terms or specialized vocabulary
4. AVOID:
   - Generic words (thing, person, place, time, way, people, things)
   - Action words or verbs (doing, making, thinking, working)
   - Adjectives or descriptive words alone
5. Use Title Case (capitalize first letter of each word)
6. Keep topics concise: 1-4 words maximum
7. If the sentence mentions fewer than {top_n} distinct topics, extract only what's present

SENTENCE: "{sentence}"

Return ONLY a JSON array with NO other text or explanation.
Format: ["Topic One", "Topic Two"]

JSON:"""

    for attempt in range(retry_count):
        try:
            response = ollama.generate(
                model=model,
                prompt=prompt,
                options={
                    'temperature': 0.3,  # Slightly higher for diversity
                    'num_predict': 100,
                    'top_p': 0.9,
                }
            )
            
            content = response['response'].strip()
            
            # Try to extract JSON array from response
            start_idx = content.find('[')
            end_idx = content.rfind(']') + 1
            
            if start_idx != -1 and end_idx > start_idx:
                json_str = content[start_idx:end_idx]
                topics = json.loads(json_str)
                
                # Format topics in Title Case
                formatted_topics = []
                for topic in topics[:top_n]:
                    # Clean and format the topic
                    topic_str = str(topic).strip()
                    if topic_str:  # Only add non-empty topics
                        # Convert to Title Case
                        formatted_topic = ' '.join(word.capitalize() for word in topic_str.split())
                        formatted_topics.append(formatted_topic)
                
                # Ensure we return at most top_n topics
                return formatted_topics[:top_n] if formatted_topics else []
            
        except json.JSONDecodeError as e:
            print(f"Attempt {attempt + 1}: JSON parsing error - {e}")
            if attempt < retry_count - 1:
                time.sleep(0.5)  # Brief pause before retry
                continue
            else:
                print(f"Failed to parse after {retry_count} attempts")
                print(f"LLM Response: {content if 'content' in locals() else 'No response'}")
                
        except Exception as e:
            print(f"Attempt {attempt + 1}: Error extracting topics - {e}")
            if attempt < retry_count - 1:
                time.sleep(0.5)
                continue
            else:
                print(f"Failed after {retry_count} attempts")
    
    # Return empty list on complete failure
    return []


def find_topics(text, model='llama3.1', top_n=2, verbose=False):
    """
    Process text and extract topics from every sentence using LLM.
    
    Args:
        text: Input text to process
        model: Ollama model name (default: 'llama3.1')
        top_n: Number of topics per sentence (default: 2)
        verbose: Print progress information (default: False)
    
    Returns:
        DataFrame with columns: ['id', 'original_sentence', 'sentence', 'terms', 'sentence_part_id']
    """
    # Tokenize into sentences
    sentences = sent_tokenize(text)
    
    if verbose:
        print(f"Processing {len(sentences)} sentences...")
    
    topic_data = []
    
    for sentence_id, sentence in enumerate(sentences, start=1):
        if verbose:
            print(f"\nSentence {sentence_id}/{len(sentences)}")
            print(f"Text: {sentence[:80]}...")
        
        part1, part2 = split_sentence(sentence)
        original_sentence = sentence
        
        if part2:
            # Sentence was split
            if verbose:
                print("  -> Split into 2 parts")
            
            # Extract topics from each part separately
            topics_part1 = extract_topics_from_sentence(part1, model=model, top_n=top_n)
            topics_part2 = extract_topics_from_sentence(part2, model=model, top_n=top_n)
            
            if verbose:
                print(f"  Part 1 topics: {topics_part1}")
                print(f"  Part 2 topics: {topics_part2}")
            
            # Add both parts with their respective topics
            topic_data.append({
                'id': sentence_id,
                'original_sentence': original_sentence,
                'sentence': part1,
                'terms': topics_part1
            })
            topic_data.append({
                'id': sentence_id,
                'original_sentence': original_sentence,
                'sentence': part2,
                'terms': topics_part2
            })
        else:
            # Single part sentence
            if verbose:
                print("  -> Single part")
            
            topics = extract_topics_from_sentence(sentence, model=model, top_n=top_n)
            
            if verbose:
                print(f"  Topics: {topics}")
            
            topic_data.append({
                'id': sentence_id,
                'original_sentence': original_sentence,
                'sentence': sentence,
                'terms': topics
            })
    
    # Create DataFrame
    df = pd.DataFrame(topic_data)
    df['sentence_part_id'] = df.index
    
    return df


def batch_process_topics(texts, model='llama3.1', top_n=2, verbose=False):
    """
    Process multiple texts and extract topics.
    
    Args:
        texts: List of text strings to process
        model: Ollama model name
        top_n: Number of topics per sentence
        verbose: Print progress
    
    Returns:
        List of DataFrames, one per input text
    """
    results = []
    
    for i, text in enumerate(texts, start=1):
        if verbose:
            print(f"\n{'='*60}")
            print(f"Processing text {i}/{len(texts)}")
            print(f"{'='*60}")
        
        df = find_topics(text, model=model, top_n=top_n, verbose=verbose)
        results.append(df)
    
    return results


# Test and demonstration
if __name__ == "__main__":
    # Test texts
    test_texts = [
        """The journey of coffee begins in tropical regions around the world, where coffee plants thrive in the shade of mountainous terrain. Countries like Ethiopia, Colombia, Brazil, and Vietnam have built entire economies around this beloved crop. Each region imparts its own unique characteristics to the beans, influenced by altitude, soil composition, and climate.""",
        
        """Quantum computing represents a groundbreaking shift in computational technology. Unlike classical computers that use bits, quantum computers use qubits which can exist in multiple states simultaneously. This property, known as superposition, allows quantum computers to process vast amounts of data in parallel."""
    ]
    
    print("="*70)
    print("TOPIC EXTRACTION FROM SENTENCES USING LLM")
    print("="*70)
    
    # Process first test text with verbose output
    print("\nTest 1: Coffee text (verbose)")
    print("-"*70)
    df1 = find_topics(test_texts[0], model='llama3.1', top_n=2, verbose=True)
    
    print("\n" + "="*70)
    print("RESULTS:")
    print("="*70)
    print(df1.to_string())
    
    # Process second test text
    print("\n\n" + "="*70)
    print("Test 2: Quantum computing text")
    print("-"*70)
    df2 = find_topics(test_texts[1], model='llama3.1', top_n=2, verbose=False)
    print(df2.to_string())
    
    # Display summary statistics
    print("\n" + "="*70)
    print("SUMMARY:")
    print("="*70)
    print(f"Test 1: {len(df1)} sentence parts processed")
    print(f"Test 2: {len(df2)} sentence parts processed")
    print(f"Total unique topics in Test 1: {len(set(term for terms in df1['terms'] for term in terms))}")
    print(f"Total unique topics in Test 2: {len(set(term for terms in df2['terms'] for term in terms))}")