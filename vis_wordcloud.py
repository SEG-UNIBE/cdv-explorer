import os
import json
from collections import Counter
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# Extracts all words from all the bip_xxxx.json's
def extract_word_frequencies(folder_path):
    word_counter = Counter()
    for file in os.listdir(folder_path):
        if file.endswith(".json"):
            file_path = os.path.join(folder_path, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                word_list = data.get("insights", {}).get("word_list", {})
                word_counter.update(word_list)
    return word_counter

# path to all json's
folder_path = "bips_json"

# extract word frequencies
word_frequencies = extract_word_frequencies(folder_path)

# create wordcloud
wordcloud = WordCloud(
    width=800, height=400,
    background_color="white",
    max_words=100
).generate_from_frequencies(word_frequencies)

# visualize wordcloud
plt.figure(figsize=(10, 5))
plt.imshow(wordcloud, interpolation="bilinear")
plt.axis("off")
plt.title("", fontsize=16)
plt.show()
