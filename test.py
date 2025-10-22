import pandas as pd
import re

# Lire le fichier
df = pd.read_excel(r"C:\Users\admin\Desktop\ttv\epi-ttv\API_US388\new_metadata_mixkit_unsplash_pixabay-4.xlsx")

def extract_keywords(text):
    if pd.isna(text) or text == "":
        return []
    text = str(text).lower()
    # Extraire mots de ['mot1', 'mot2']
    words = re.findall(r"'([^']+)'", text)
    if not words:
        words = re.findall(r'\w+', text)
    return [w.strip() for w in words if len(w) > 2]

# Filtrer
def is_coherent(row):
    if pd.isna(row['description']) or pd.isna(row['keywords_description']) or \
       pd.isna(row['keywords']) or pd.isna(row['new_description']):
        return False
    
    all_words = (extract_keywords(row['description']) + 
                 extract_keywords(row['keywords_description']) + 
                 extract_keywords(row['keywords']) + 
                 extract_keywords(row['new_description']))
    
    freq = {}
    for w in all_words:
        freq[w] = freq.get(w, 0) + 1
    
    return sum(1 for c in freq.values() if c >= 2) >= 2

coherent = df[df.apply(is_coherent, axis=1)]
coherent.to_excel('images_coherentes_filtrees.xlsx', index=False)
print(f"✅ {len(coherent)} images cohérentes extraites!")