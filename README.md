# Audio Stem Splitter

A sleek, modern web application that uses AI to separate audio tracks into individual stems (vocals, drums, bass, piano, and more).

![Python](https://img.shields.io/badge/Python-3.10-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-green)
![Spleeter](https://img.shields.io/badge/Spleeter-2.4+-purple)

## Features

- **Upload audio files** (MP3, WAV, FLAC, etc.) or **paste URLs** from YouTube, SoundCloud, and other platforms
- **Audio preview** with interactive waveform visualization (powered by WaveSurfer.js)
- **BPM detection** using librosa
- **Cover art & metadata** display for URL fetches
- **Stem separation** with 2, 4, or 5 stem options:
  - **2 stems**: Vocals + Accompaniment
  - **4 stems**: Vocals, Drums, Bass, Other
  - **5 stems**: Vocals, Drums, Bass, Piano, Other
- **Interactive waveform players** for each separated stem
- **Download** individual stems as WAV files

## Prerequisites

- [Conda](https://docs.conda.io/en/latest/miniconda.html) (Miniconda or Anaconda)
- [FFmpeg](https://ffmpeg.org/download.html) (required for audio processing)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/nick-mccarty/spleeter-web.git
cd spleeter-web
```

### 2. Create and activate a Conda environment

```bash
conda create -n spleeter-web python=3.10 -y
conda activate spleeter-web
```

### 3. Install FFmpeg

```bash
conda install -c conda-forge ffmpeg -y
```

### 4. Install Spleeter and dependencies

```bash
# Install spleeter via poetry
git clone https://github.com/Deezer/spleeter
cd spleeter
pip install poetry
poetry install

# Install additional web app dependencies
cd ..
pip install -r requirements.txt
```

## Running the Application

```bash
cd spleeter
poetry run python -m uvicorn app.main:app --reload --app-dir ..
```

Then open http://localhost:8000 in your browser.

## Usage

1. **Upload or fetch audio**
   - Drag & drop an audio file, or
   - Paste a URL and click "Fetch Audio"

2. **Preview your track**
   - See the waveform visualization
   - Check the detected BPM
   - Play/pause to preview

3. **Select stem count** (2, 4, or 5 stems)

4. **Click "Split Audio"** and wait for processing

5. **Explore your stems**
   - Each stem has its own waveform player
   - Click to seek, play/pause individual stems
   - Download as WAV files

## Project Structure

```
spleeter-web/
├── app/
│   ├── main.py              # FastAPI application
│   ├── templates/
│   │   └── index.html       # Web interface
│   ├── static/              # Static assets
│   ├── uploads/             # Uploaded files (gitignored)
│   └── output/              # Separated stems (gitignored)
├── spleeter/                # Spleeter library (submodule/clone)
├── requirements.txt         # Python dependencies
└── README.md
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Web interface |
| POST | `/analyze` | Analyze audio file (returns BPM) |
| POST | `/fetch-url` | Download & analyze audio from URL |
| POST | `/upload` | Start stem separation job |
| GET | `/status/{job_id}` | Check job status |
| DELETE | `/job/{job_id}` | Clean up job files |

## Technologies

- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern Python web framework
- **[Spleeter](https://github.com/deezer/spleeter)** - AI-powered audio source separation by Deezer
- **[WaveSurfer.js](https://wavesurfer.xyz/)** - Interactive waveform visualization
- **[librosa](https://librosa.org/)** - Audio analysis and BPM detection
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - Download audio from various platforms
- **[Tailwind CSS](https://tailwindcss.com/)** - Utility-first CSS framework

## Troubleshooting

### FFmpeg not found

```bash
conda install -c conda-forge ffmpeg -y
```

### TensorFlow errors

```bash
pip uninstall tensorflow
pip install tensorflow==2.12.1
```

### Memory errors on large files

For very long audio files, consider processing shorter clips or using a machine with more RAM.

## License

This project uses Spleeter which is licensed under the MIT License by Deezer.
