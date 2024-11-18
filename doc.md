# Documentation

## Requirements
- **`github_token.txt`**: Just paste a github token inside this file

## Main.py
Manages all the logic

## Download.py
Downloads all BIP's as *.md or *.mediawiki files & also downloads all associated files for each BIP. 
All files are saved into __bips_downloaded__. 
Associated files are saved into the corresponding __bips_downloaded/bips_xxxx__ folder.

## preamble_extraction.py
The <code>< pre>...< /pre></code> block gets extracted out of every .md/.mediawiki files inside the __bips_downloaded__ folder.
It differentiates between the required fields and the optional fields.
If you have multi-line fields as they often appear in 'author' and 'licences', it adds a list to the corresponding key.
The extracted information inside the preamble gets placed in the __preamble__ section inside the JSON file.
All JSON files get saved in __bips_json__.

## bip_processor.py
Adds metadata and insights about each BIP to the corresponding JSON file. For the metadata, it adds
### Metadata
- **`last_commit`**: The date of the most recent commit for the BIP file (ISO 8601 format).
- **`total_commits`**: The total number of commits made to the BIP file.
- **`metadata_last_updated`**: The timestamp (ISO 8601 format) indicating when the metadata was last updated.
- **`git_history`**: A list of tuples containing the Git commit hash, date, and author for each commit in the BIP's history.
- **`contributors`**: The total number of unique contributors to the BIP file.
- **`google_trend_index`**: Placeholder for storing Google Trends data (not implemented yet).
### Insights
#### Compliance Section
- **`title_length_respected`**: Indicates whether the BIP title length adheres to the 44-character limit (`true`/`false`).
- **`title_length`**: The actual length of the BIP title in characters.
- **`abstract_length_respected`**: Indicates whether the word count of the "Abstract" section is within the limit of 200 words (`true`/`false`).
- **`abstract_word_count`**: The total word count of the "Abstract" section.
- **`created_date_format_correct`**: Indicates whether the `created` field in the preamble follows the ISO 8601 date format (`true`/`false`).
- **`required_fields_present`**: Indicates whether all required fields in the preamble are present and non-null (`true`/`false`).
- **`missing_fields`**: A list of required fields that are missing or null.
- **`layer_valid`**: Indicates whether the `layer` field in the preamble contains a valid value (`true`/`false`).

#### Word List Section
- **`word_list`**: A dictionary of words extracted from the raw content of the BIP file (excluding stop words). Each word is a key, and its frequency is the value, sorted in descending order of frequency.

# Todo
### General
- [ ] Required / Used BIPS might also appear in the text of the BIP instead of the intended field in the preamble. Search via LLM through content of bips for such cases.
### preamble_extraction.py
- [x] If optional field is not existent, still add it to the json structure, such that the JSON is uniform in structure.
- [x] Create Raw section
  - [x] Put preamble into Raw section
### bip_processor.py --> section metadata
- [ ] Add these datapoints to metadata
  - [x] Last commit (yyyy_mm_dd_hh_mm_ss or same timestamp as in preamble)  (currently done in get_commit_info())
  - [x] Total amount of commits
  - [x] Metadata last updated
  - [x] Git history (list of [commit_hash, date, author])
  - [ ] Google Trend index 
  
### bip_processor.py --> section insights
- [ ] Compliance section
  - [x] Adjust analysis path so it now checks for preamble in the raw section
    - [x] Refine list of standards which should be upheld in the preamble. (Better naming, clearer checks)
    - [ ] Create list of all standards checked with proper description in doc.md
    - [ ] In compliance wit BIP_2/_123 (all standards need to be met) 
        - [x] Length of title respected
        - [x] Length of abstract respected
        - [x] Date format of 'created' correct
        - [x] All required fields present
          - [x] Missing fields
        - [ ] Is doc structure correct (headlines / subsections)
          - [ ] Missing headlines (list)
          - [ ] Additional headlines (list)
          - [ ] Wrong depth (list)
- [ ] Create function which checks the bips structure (ambivalent for .md/.mediawiki)
  - [ ] Save doc structure in section 'raw/docstruct' in a useful/informative way
    - [ ] Figure out best structure to save docstruct
- [x] Create function which creates wordmap of each BIP and places it into section 'raw/wordmap'
- [ ] Improve wordlist function and adjust stop word list
### visualization.py
- [ ] Create a dynamic html file with the bips as content (plotly.js)