# YouMark

YouMark is a Flask-based API that processes YouTube video transcripts, cleans and refines user queries using Gemini AI, and identifies relevant segments from the transcript based on user-provided queries.

## Features
- **Transcript Retrieval**: Fetch transcripts for YouTube videos using `youtube_transcript_api`.
- **Query Refinement**: Cleans and refines user queries using the Gemini AI model.
- **Segment Processing**: Processes video transcripts into lemmatized and cleaned text segments.
- **Keyword Extraction**: Extracts keywords from user queries using SpaCy's NLP capabilities.
- **Relevance Matching**: Identifies and ranks relevant transcript segments based on user queries.
- **CORS Enabled**: Supports cross-origin requests for easy integration.

---

## Prerequisites
- Python 3.8 or higher
- Gemini AI API Key

---

## Installation

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/<your-repo-name>/YouMark.git
   cd YouMark
