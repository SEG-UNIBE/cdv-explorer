# Todo
### General
- [ ] Required / Used BIPS might also appear in the text of the BIP instead of the intended field in the preamble. Search via LLM through content of bips for such cases.
### preamble_extraction.py
- [x] If optional field is not existent, still add it to the json structure, such that the JSON is uniform in structure.
- [x] Create Raw section
  - [x] Put preamble into Raw section
### bip_processor.py --> section metadata
- [ ] Add these datapoints to metadata
  - [ ] Correct the contributors (Also add authors of the BIP to list of unique authors; Currently only authors of commits counted)
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
- [ ] Automatically link all the dots to either github.com/bitcoin/bips/corresponding_BIP or to bips.dev/xxxx, so if you want to look into one, you can click on the dot on the visualization.
- [ ] Improve wordlist function and adjust stop word list
### visualization.py
- [ ] Create a dynamic html file with the bips as content (plotly.js)
