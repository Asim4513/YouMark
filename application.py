from flask import Flask, jsonify, request
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled
import re
import spacy
from flask_cors import CORS
import functools
from spacy.tokens import Doc
import requests
import os
import openai
import contractions
from spellchecker import SpellChecker
from pprint import pprint
import nltk
from nltk.corpus import wordnet as wn
import time
import google.generativeai as genai

application = Flask(__name__)
CORS(application)

@application.route('/')
def home():
    return "Welcome to the API!"    

# Load the NLP model from spaCy
nlp = spacy.load("en_core_web_sm")


api_key = 'AIzaSyDHwb27elDP7jjr2Yqx98hKFMJi82SYiaY'
youtube = build('youtube', 'v3', developerKey=api_key)

genai.configure(api_key="AIzaSyDD88fdydCXN21a9ALQbrqLw2YZAKkMpy4")

@functools.lru_cache(maxsize=50)
def sbert_embed_text(text):
    return sbert_model.encode([text], convert_to_tensor=True)


def extract_keywords(text):
    """Extract all lemmatized tokens from the text as keywords."""
    doc = nlp(text)
    keywords = [token.lemma_ for token in doc]  # Extract lemma for all tokens
    return keywords

def get_video_id_from_url(url):
    """Extract video ID from URL using regular expressions."""
    regex = r"(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:[^\/\n\s]+\/\S+\/|(?:v|e(?:mbed)?)\/|\S*?[?&]v=)|youtu\.be\/)([a-zA-Z0-9_-]{11})"
    matches = re.search(regex, url)
    return matches.group(1) if matches else None

def get_transcript(video_id):
    """Retrieve the transcript of a video using the YouTube Transcript API."""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return transcript
    except TranscriptsDisabled:
        return "Transcript not available for this video."
    except Exception as e:
        print(f"Failed to fetch transcript: {e}")
        return "Failed to fetch transcript."


@application.route('/process_video', methods=['POST'])
def process_video():
    data = request.get_json()
    video_id = data['video_id']
    user_query = data['query']
    user_query = clean_query_with_gpt(user_query)
    print('User query : ', user_query)
    segments = process_video_function(video_id, user_query)
    
    # Convert float values to strings
    keys_to_convert = ['similarity', 'duration', 'start_time']
    segments = [{k: str(v) if k in keys_to_convert else v for k, v in entry.items()} for entry in segments]
    return jsonify(segments)


def process_segment_text(text):
    # Using SpaCy to tokenize, lemmatize, and remove punctuation from the segment text
    doc = nlp(text.lower())  # Ensuring it's lowercase
    lemmatized_text = ' '.join(token.lemma_ for token in doc if token.pos_ not in ['PUNCT'])
    return lemmatized_text

# Improved Segmenting Function with Optimized Text Concatenation
def segment_transcript(transcript):
    """Segment the transcript into individual entries, each as a separate segment, and lemmatize the text."""
    segments = []
    for entry in transcript:
        # Process each entry's text
        processed_text = process_segment_text(entry['text'])
        new_segment = {
            'text': processed_text,
            'start_time': entry['start'],
            'duration': entry['duration']
        }
        segments.append(new_segment)
    return segments

def enhance_query_universal(query):
    # Split the query into individual words
    words = query.split()
    enhanced_query_set = set()

    # Process each word separately
    for word in words:
        synonyms = set()
        for synset in wn.synsets(word):
            for lemma in synset.lemmas():
                # Add the synonym, replacing underscores with spaces for multi-word terms
                synonyms.add(lemma.name().replace('_', ' '))

        # If synonyms were found, add them to the enhanced query set
        if synonyms:
            enhanced_query_set.update(synonyms)
        else:
            # If no synonyms found, add the original word
            enhanced_query_set.add(word)

    # Ensure the original words are included
    enhanced_query_set.update(words)

    return ' '.join(sorted(enhanced_query_set))

def query_gpt_model(prompt):
    api_key = "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"  # Replace with your actual OpenAI API key
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': "gpt-4o-mini",  # Ensure the model ID is correct
        'messages': [{"role": "system", "content": prompt}]
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers)
        response.raise_for_status()
        results = response.json()['choices']
        relevancies = []
        print("Results: ", results)
        for result in results:
            content = result['message']['content']
            print("Full response content:", content)
            # Parse each line for 'yes' to determine relevance
            relevancies.extend(['yes' in line.split(': ')[1].strip().lower() for line in content.split('\n') if ':' in line])
        return relevancies
    except requests.RequestException as e:
        print(f"Error in GPT API call: {e}")
        return []


genai.configure(api_key="AIzaSyDD88fdydCXN21a9ALQbrqLw2YZAKkMpy4")

def query_gemini_model(prompt, model_name="gemini-1.5-flash"):
    try:
        # Initialize the model
        model = genai.GenerativeModel(model_name)

        # Send content generation request
        response = model.generate_content(prompt)

        # Parse the response to mimic the relevancy extraction logic
        lines = response.text.split('\n')
        relevancies = [
            'yes' in line.split(': ')[1].strip().lower()
            for line in lines if ':' in line
        ]

        # Debug: Show parsed relevancies
        print("Relevancies extracted: ", relevancies)
        return relevancies
    except Exception as e:
        # Handle exceptions gracefully
        print(f"Error in Gemini API call: {e}")
        return []



def clean_query_with_gpt(original_query):
    api_key = "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"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': "gpt-4o-mini",
        'messages': [{"role": "system", "content": f"Spell correct the query and return only the corrected query : {original_query} "}]
    }

    try:
        response = requests.post("https://api.openai.com/v1/chat/completions", json=data, headers=headers)
        response.raise_for_status()
        print("Enhance full query : ", response.json()['choices'][0])
        refined_query = response.json()['choices'][0]['message']['content'].strip()
        print("Refined Query:", refined_query)
        return refined_query
    except requests.RequestException as e:
        print(f"Error in GPT API call: {e}")
        return original_query  # Fallback to original query in case of an error


def find_all_relevant_segments(segments, query):
    # Extract lemmatized words from the query
    enhanced_query = enhance_query_universal(query)
    query_doc = nlp(enhanced_query.lower())
    lemmatized_query_words = {token.lemma_ for token in query_doc if not token.is_stop and token.pos_ in ['NOUN', 'PROPN', 'VERB']}
    
    # Initialize lists to collect all segments that potentially relate to the query
    relevant_segments = []
    original_query_matches = []
    lemmatized_query_matches = []
    
    # Collect segments that match the original query words
    for segment in segments:
        segment_text = segment['text'].lower()
        if any(word in segment_text for word in query.split()):
            original_query_matches.append(segment)
    
    # Collect segments that match the lemmatized query words
    for segment in segments:
        segment_text = segment['text'].lower()
        if any(word in segment_text for word in lemmatized_query_words):
            lemmatized_query_matches.append(segment)

    # Define threshold for outlier detection
    threshold = 0.2 * len(segments)  # For example, more than 50% of segments is considered unusually high

    # Append matches to the batch
    batch = original_query_matches
    if len(lemmatized_query_matches) <= threshold:
        batch.extend(lemmatized_query_matches)

    # Ensure there are always at least two segments to process
    if len(batch) == 1:
        segment_index = segments.index(batch[0])
        if segment_index > 0:
            batch.insert(0, segments[segment_index - 1])
        elif segment_index < len(segments) - 1:
            batch.append(segments[segment_index + 1])

    # Process all collected segments in one batch if there are any
    if batch:
        relevant_segments.extend(query_batch(batch, query))
    
    return relevant_segments


def query_batch(batch, query):
    def process_subbatch(subbatch):
        # Construct a prompt for the subbatch
        prompt = f"Please review each segment carefully. For each one, decide if it contains information that answers or relates to the query '{query}'. Respond with '1: yes' if it does, '1: no' if it does not, followed by '2: yes/no', and so on for each segment. If it does, even partially or indirectly, please respond with 'yes'. If it definitely does not contain relevant information, respond with 'no'. Consider the broader context of the query when making your decision. Here are the segments:\n"
        prompt += '\n'.join([f"{idx + 1}: {seg['text']}" for idx, seg in enumerate(subbatch)])
        
        # Query the model for relevance
        model_responses = query_gemini_model(prompt)  # This needs to be defined or replaced with actual call
        if model_responses:
            # Filter segments based on model responses
            for idx, seg in enumerate(subbatch):
                if model_responses[idx]:  # Assuming model_responses aligns with subbatch order
                    seg['similarity'] = 0.99  # Assign a high similarity score for relevant segments
                else:
                    seg['similarity'] = 0.01  # Assign a low similarity score for irrelevant segments
            return [seg for seg in subbatch if seg['similarity'] > 0.5]  # Only return relevant segments
        return []  # Return an empty list if no relevant segments are found or model call fails

    # Split the batch into subbatches of 15
    subbatches = [batch[i:i + 15] for i in range(0, len(batch), 15)]
    relevant_segments = []
    for subbatch in subbatches:
        print("Subbatch : ", subbatch)
        relevant_segments.extend(process_subbatch(subbatch))

    return relevant_segments


# Dummy route for testing
@application.route('/get_segments', methods=['POST'])
def get_segments():
    # Here you would integrate your Python code that processes the video ID or URL
    video_id = request.json.get('video_id')
    # Imagine this function fetches and processes the video to find relevant segments
    segments = process_video(video_id)  # You would define this function
    return jsonify(segments)


def process_video_function(video_id, user_query):
    transcript = get_transcript(video_id)
    if not isinstance(transcript, str):
        segments = segment_transcript(transcript)
        keywords = extract_keywords(user_query)
        search_query = ' '.join(keywords)

        # Only find relevant segments if the transcript is successfully segmented
        relevant_segments = find_all_relevant_segments(segments, search_query)
        relevant_segments = sorted(relevant_segments, key=lambda x: x.get('similarity', 0), reverse=True)

        if relevant_segments:
            print("Relevant segments found:")
            for segment in relevant_segments:
                print(f"\nSegment starting at {segment['start_time']} seconds (Duration: {segment['duration']} seconds)")
                print(f"Relevance Score: {segment['similarity']:.3f}")
                print(f"Text: {segment['text']}")
        else:
            print("No relevant segments found.")
    else:
        print(transcript)

    return relevant_segments if isinstance(relevant_segments, list) else []

if __name__ == '__main__':
    application.run(debug=True, port=5000)
