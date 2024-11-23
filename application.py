from flask import Flask, jsonify, request
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled
import re
import spacy
from flask_cors import CORS
import functools
import requests
import os
import nltk
from nltk.corpus import wordnet as wn
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

def extract_keywords(text):
    """Extract all lemmatized tokens from the text as keywords."""
    doc = nlp(text)
    keywords = [token.lemma_ for token in doc]  # Extract lemma for all tokens
    return keywords

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
    user_query = clean_query_with_gemini(user_query)
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

def query_gemini_model(prompt, model_name="gemini-1.5-flash"):
    try:
        # Initialize the model
        model = genai.GenerativeModel(model_name)

        # Send the content generation request
        response = model.generate_content(prompt)

        # Parse the response to extract relevance
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


def clean_query_with_gemini(original_query):
    try:
        # Initialize the Gemini model
        model = genai.GenerativeModel("gemini-1.5-flash")  # Replace with the correct Gemini model name if needed

        # Create the prompt for the model
        prompt = f"Spell correct the query and return only the corrected query: {original_query}"

        # Send the content generation request
        response = model.generate_content(prompt)

        # Extract the corrected query from the response
        if hasattr(response, 'text') and response.text.strip():
            refined_query = response.text.strip()
            print("Refined Query:", refined_query)
            return refined_query
        else:
            print("Gemini response is empty or invalid.")
            return original_query  # Fallback to original query

    except Exception as e:
        # Handle exceptions gracefully
        print(f"Error in Gemini API call: {e}")
        return original_query  # Fallback to original query in case of an error
    

def find_all_relevant_segments(segments, query):
    # Extract lemmatized words from the query
    enhanced_query = enhance_query_universal(query)
    query_doc = nlp(enhanced_query.lower())
    lemmatized_query_words = {token.lemma_ for token in query_doc if not token.is_stop and token.pos_ in ['NOUN', 'PROPN', 'VERB']}
    
    # Preprocess segments once for efficiency
    preprocessed_segments = [
        {
            'text': seg.get('text', '[No text available]'),
            'lower_text': seg.get('text', '').lower(),
            'start_time': seg.get('start_time', 0),  # Default to 0 if missing
            'duration': seg.get('duration', 0),  # Default to 0 if missing
        }
        for seg in segments
    ]
    
    # Collect matches based on the original query words
    query_words = set(query.lower().split())
    original_query_matches = [
        seg for seg in preprocessed_segments if query_words.intersection(seg['lower_text'].split())
    ]
    
    # Collect matches based on the lemmatized query words
    lemmatized_query_matches = [
        seg for seg in preprocessed_segments if lemmatized_query_words.intersection(seg['lower_text'].split())
    ]

    # Define threshold for outlier detection
    threshold = 0.2 * len(segments)
    
    # Prepare the final batch
    batch = original_query_matches
    if len(lemmatized_query_matches) <= threshold:
        batch.extend(seg for seg in lemmatized_query_matches if seg not in batch)

    # Ensure there are at least two segments for processing
    if len(batch) == 1:
        segment_index = next((i for i, seg in enumerate(preprocessed_segments) if seg == batch[0]), -1)
        if segment_index > 0:
            batch.insert(0, preprocessed_segments[segment_index - 1])
        elif segment_index < len(preprocessed_segments) - 1:
            batch.append(preprocessed_segments[segment_index + 1])
    
    # Process the batch for relevance
    relevant_segments = query_batch(batch, query) if batch else []
    
    return relevant_segments


def query_batch(batch, query):
    def process_subbatch(subbatch):
        # Construct a prompt for the subbatch
        prompt = f"Please review each segment carefully. For each one, decide if it contains information that answers or relates to the query '{query}'. Respond with '1: yes' if it does, '1: no' if it does not, followed by '2: yes/no', and so on for each segment. If it does, even partially or indirectly, please respond with 'yes'. If it definitely does not contain relevant information, respond with 'no'. Consider the broader context of the query when making your decision. Here are the segments:\n"
        prompt += '\n'.join([f"{idx + 1}: {seg['text']}" for idx, seg in enumerate(subbatch)])
        
        # Query the model for relevance
        model_responses = query_gemini_model(prompt)
        if model_responses:
            return [
                {**seg, 'similarity': 0.99} if model_responses[idx] else {**seg, 'similarity': 0.01}
                for idx, seg in enumerate(subbatch)
            ]
        return []

    # Divide the batch into subbatches and process them
    relevant_segments = []
    for i in range(0, len(batch), 15):  # Process in chunks of 15 to optimize prompt size
        subbatch = batch[i:i + 15]
        relevant_segments.extend([
            seg for seg in process_subbatch(subbatch) if seg.get('similarity', 0) > 0.5
        ])

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
