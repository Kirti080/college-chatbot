import speech_recognition as sr
import datetime
import webbrowser
import os
import pandas as pd
import google.generativeai as genai
from difflib import get_close_matches
import requests
import base64
from pydub import AudioSegment
import simpleaudio as sa
import io
import traceback  # <-- for better error logging
import tempfile
import pygame

# 🔐 API Keys
genai.configure(api_key="AIzaSyCPWTq7pyJWg1lcVD2Mh-V0-R_eyCOlY8k")
TTS_API_KEY = "AIzaSyBHbl-pCyU4q_akVo8Hiwv8Ko_RdggVF9g"

# 🤖 Gemini model
model = genai.GenerativeModel(model_name="models/gemini-1.5-flash")

# 📄 Load Excel Q&A
qa_df = pd.read_excel("college_questions.xlsx")
qa_dict = dict(zip(qa_df['Question'].str.lower(), qa_df['Answer']))


def speak_google_tts_realtime(text):
    try:
        print("Assistant:", text)

        # Optional: Send to local UI if needed
        try:
            requests.post("http://localhost:5005/speak", json={"text": text})
        except:
            print("⚠ UI server not reachable.")

        # TTS API
        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={TTS_API_KEY}"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": "en-IN",
                "name": "en-IN-Wavenet-B",
                "ssmlGender": "FEMALE"
            },
            "audioConfig": {"audioEncoding": "MP3"}
        }

        # Get response
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        audio_content = base64.b64decode(response.json()['audioContent'])

        # Save to temp .mp3 file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as f:
            f.write(audio_content)
            temp_file_path = f.name

        # Play using pygame
        pygame.mixer.init()
        pygame.mixer.music.load(temp_file_path)
        pygame.mixer.music.play()

        # Wait until finished
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)

    except Exception as e:
        print("❌ Error in speak_google_tts_realtime():", str(e))
        traceback.print_exc()



# 🎧 Voice listener
def listen():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎙 Listening...")
        r.pause_threshold = 0.5
        audio = r.listen(source)
    try:
        print("🧠 Recognizing...")
        query = r.recognize_google(audio)
        print("You said:", query)
        return query.lower()
    except:
        print("❌ Could not recognize.")
        return ""

# 🧠 Excel-based answer lookup
def get_custom_answer(user_query):
    match = get_close_matches(user_query, list(qa_dict.keys()), n=1, cutoff=0.7)
    return qa_dict[match[0]] if match else None

# 💬 Gemini reply fallback
def get_gemini_reply(prompt):
    try:
        full_prompt = f"{prompt}\n\nPlease answer briefly in 1-2 lines."
        response = model.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        print("❌ Error with Gemini API:", str(e))
        traceback.print_exc()
        return "Sorry, Gemini API failed to respond."

# 👋 Greet user
def greet_user():
    hour = datetime.datetime.now().hour
    greeting = "Good morning!" if hour < 12 else "Good afternoon!" if hour < 18 else "Good evening!"
    speak_google_tts_realtime(greeting)
    speak_google_tts_realtime("I am your smart assistant. Ask me anything.")

# 🔁 Main assistant loop
if __name__ == "__main__":
    greet_user()

    while True:
        try:
            query = listen()
            if not query:
                continue

            if "open youtube" in query:
                webbrowser.open("https://www.youtube.com")
                speak_google_tts_realtime("Opening YouTube.")
            elif "open google" in query:
                webbrowser.open("https://www.google.com")
                speak_google_tts_realtime("Opening Google.")
            elif "play music" in query:
                music_dir = "C:\\Users\\Public\\Music"  # Adjust for your PC
                songs = os.listdir(music_dir)
                if songs:
                    song_path = os.path.join(music_dir, songs[0])
                    os.startfile(song_path)
                    speak_google_tts_realtime("Playing music.")
                else:
                    speak_google_tts_realtime("No music found.")
            elif "exit" in query or "stop" in query:
                speak_google_tts_realtime("Goodbye! Have a nice day! ")
                break
            else:
                answer = get_custom_answer(query)
                reply = answer if answer else get_gemini_reply(query)
                speak_google_tts_realtime(reply)

        except Exception as e:
            print("❌ Error in main loop:", str(e))
            traceback.print_exc()