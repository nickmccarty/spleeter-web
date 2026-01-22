"""
Audio analysis utilities for extracting metadata from audio files.
"""
import soundfile as sf
import librosa


def get_audio_duration(file_path: str) -> float:
    """
    Get the duration of an audio file in seconds.

    Uses soundfile for efficient duration extraction without loading entire file.
    """
    info = sf.info(file_path)
    return info.duration


def get_audio_bpm(file_path: str) -> float:
    """
    Analyze audio file to extract BPM (tempo).

    Uses librosa for beat detection.
    """
    y, sr = librosa.load(file_path, sr=None)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)[0]
    return float(tempo)


def analyze_track(file_path: str) -> dict:
    """
    Analyze an audio file to extract BPM and duration.

    Returns a dictionary with 'bpm' and 'duration' keys.
    """
    duration = get_audio_duration(file_path)
    bpm = get_audio_bpm(file_path)

    return {
        "bpm": bpm,
        "duration": duration
    }
