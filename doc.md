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

## Meeting notes 20.11.2024 (What to show in the presentation)
- What's a BIP
- Visualizations 
- Insights (Show why we actually did all the scraping, so we can then analyze it) 3 insights
  - preamble violations
  - docstructure not correct
  - wordclouds
  - file formats (md or mediawiki)
- Future work
  - Extend meta (google trend index)
  - extend insights (via llm) 
    - (dependency tree)
      - Preamble dependencies & in-text referneces on required bips
        - Can be shown that even when we have requirements in preamble, some don't seem to care and just write it in text
  - Chronical evolution
    - If we run the pipeline for a long time, then we can track on how things run (based on git history)
  - extend search space ( Github, .., lightning/LIPS, SLIPs (Satoshi Lab improvement proposals))
  - Backup slides
    - Screenshots of pipeline (Code)
    - Painpoints/lessons learned

[ ] Löse Bug mit Titel problem
  - BIP 372 has in preamble in required BIP-174 instead of just 174, which leads to the display problem

[x] Überprüfe alle required links (ob vollständig)
  - Actually all are correct and there are just not more of them

[ ] Vervollständige requirements.txt vom venv
      pip3 freeze > requirements.txt

[ ] extend documentation on what commands to run



## Präsi

### Whats a BIP? (5min)
- Bitcoin is just code
  - Basic description of Bitcoin
    - Distributed and decentralized system
    - No king, big community
  - Needs to be organised in some way or another
    - How is this done?
- BIPS!
  - Show Github and bips.dev page to show how much data there is 
  - We have different kinds of BIPs 
    - Standard Track Bips
      - Consensus
      - Peer Service
      - API/RCP
      - Application
      - Example BIP 141 SegWit
    - Informational BIPs
      - Not directly change protocol, but rather provide useful information, new ideas, concepts, methodologies
      - Example Bip 39 Mnemonic phrase to deterministically generate wallets
    - Process BIPs
      - Describes changes or improvements to the process by which Bitcoin software and protocol upgrades are developed, tested & implemented
      - Example BIP 2 How to write a BIP

### Talk about BIP 2 (2.5min)
- What does BIP 2 say?
  - It predefines how to write a BIP with all the steps you need to go through with the editors etc. but it also specifies a multitude of standards
  - Specifications
    - Preamble
    - Abstract
    - Copyright
    - Specifications
    - Motivations
    - Rationale
    - Backwards Compatibility
    - Reference Implementation
  - Preamble is important for us
    - Look at all the possible fields in the preamble, with required and optional ones, show possible states of certain fields etc. e.g. x requires y, x supersedes y etc.
  - (Talking about this all makes sense, once we go to the next slide where we now visualize the whole data points we just talked about)

### Visualisation (ca. 3min)
- Live demo of dash app
  - Show how it looks
  - Shortly describe what you see. All BIPs on one page where you can easily hover over everything
  - Explain arrows and lines, zoom in to show it a bit more clearly
  - Show colors and how you can filter for certain statuses
  - Explain node scaling
  - Show wordcloud (if I can fix it until presentation)
  - Shortly show BIP 173 and 350 where 350 replaces 173, but 173 is still final and not replaced in its status and now go over to insights and make the bridge with this example to be able to have certain insights with such a data visualization

### Insights (length?)
- Shortly explain what was done to achieve such a visualization
  - Pipeline setup
    - Scraping everything and processing it into JSON
    - Create insights, metadata and more
    - Show JSON
- What can now be done with this data?
  - Preamble violations
    - Check to see if all the standards are met in the BIPs according to BIP 2 and BIP 123
    - Show some examples
      - Titles too long
      - No licences --> Mostly just with BIPs which have been withdrawn
  - Analyze doc structure
    - Check if all the headlines are in the right order and according to standards
  - Wordcloud
  - File formats
  - Was just a showcase, could be extended however people like. The idea of this whole scraping and data aggregation is to provide it to other people, so they can then work with the data however they like

### Future work (length??)
- Shortly talk about setup of data pipeline and how it is easy extendable with other functions which feed data into JSON
- But then show some more concrete examples of possible future work
  - Extend metadata with google trend index, which could be plotted to see which BIPs were prominent for a short time, which ones for a long time/continuously
  - Extend insights via LLMs
    - Use LLMs to go through text and find required BIPs which are just mentioned in the text instead of preamble
  - Extend search space for Improvement proposals to other souces next to BIPs. There are similare things like LIPs and SLIPs

### Backup slides
- Make a data pipeline diagram where whole schematic is shown 
- Make a short overview to display how easy it is to download everything with basically just a click of a button
- Pain points
  - 