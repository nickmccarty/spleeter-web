# Audio Stem Splitter

A sleek, modern web application that uses AI to separate audio tracks into individual stems (vocals, drums, bass, piano, and more).

![Python](https://img.shields.io/badge/Python-3.10-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.95+-green)
![Spleeter](https://img.shields.io/badge/Spleeter-2.4+-purple)

> For detailed technical documentation including data flow diagrams, database schemas, and API specifications, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Features

### Audio Input
- **Upload audio files** (MP3, WAV, FLAC, etc.) or **paste URLs** from YouTube, SoundCloud, and other platforms
- **Audio preview** with interactive waveform visualization (powered by WaveSurfer.js)
- **BPM detection** using librosa
- **Cover art & metadata** display for URL fetches

### Stem Separation
- **2 stems**: Vocals + Accompaniment
- **4 stems**: Vocals, Drums, Bass, Other
- **5 stems**: Vocals, Drums, Bass, Piano, Other
- **Interactive waveform players** for each separated stem
- **Download** individual stems as WAV files

### Crate (Track Library)
- **Persistent storage** of all processed tracks using SQLite
- **Expandable track rows** showing metadata (BPM, duration, stem count)
- **Original track** available for sampling alongside separated stems
- **Quick access** to all stems with waveform visualization
- **Delete tracks** when no longer needed

### Samples
- **Region selection** - Shift + drag on any waveform to select a portion
- **Visual feedback** - see the selection region in real-time as you drag
- **Precision tooltip** showing time in M:SS.mmm format for accurate slicing
- **Loop preview** - instantly preview your selection on loop before saving
- **One-click extraction** - save selected regions as new audio files
- **Sample library** - all created samples displayed with playback controls
- **Keyboard shortcuts** - Esc to clear selection and stop loop preview

### Loops
- **Create loops** from any stem or sample region
- **Adjustable loop count** (x2, x4, x8, x16)
- **Loop library** - all created loops displayed with waveform visualization
- **Download loops** as WAV files for use in DAWs

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
# Install web app dependencies
pip install -r requirements.txt

# Install additional spleeter dependency via poetry
git clone https://github.com/Deezer/spleeter
cd spleeter
pip install poetry
poetry install
```

## Running the Application

```bash
cd spleeter
poetry run python -m uvicorn app.main:app --reload --app-dir ..
```

Then open http://localhost:8000 in your browser.

## Usage

### Splitting Audio

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

### Working with the Crate

- All processed tracks are automatically saved to your **Crate**
- Click a track row to expand and view its stems
- Each stem shows an interactive waveform with playback controls
- Tracks persist across sessions (stored in SQLite)

### Creating Samples

1. Expand a track in the Crate to view stems
2. **Shift + drag** on any waveform to select a region (visual preview shows in real-time)
3. Use the precision tooltip (M:SS.mmm) for accurate timing
4. Click the **loop icon** in the popup to preview your selection on loop
5. Drag the region edges to fine-tune while listening
6. Click the **Sample** button to extract and download the selection
7. Press **Esc** to clear selection or stop loop preview
8. All samples appear in the **Samples** section

### Creating Loops

1. Select a region on a stem waveform, or use an existing sample
2. Choose the loop multiplier (x2, x4, x8, x16)
3. Click the checkmark button to create the loop
4. Loops are saved to the **Loops** section with waveform preview

## Project Structure

```
spleeter-web/
├── app/
│   ├── main.py              # FastAPI application
│   ├── database.py          # SQLite database management
│   ├── audio_utils.py       # Audio analysis utilities
│   ├── templates/
│   │   └── index.html       # Web interface
│   ├── static/              # Static assets
│   ├── uploads/             # Uploaded files (gitignored)
│   ├── output/              # Separated stems + originals (gitignored)
│   ├── samples/             # Extracted samples (gitignored)
│   ├── loops/               # Created loops (gitignored)
│   └── spleeter.db          # SQLite database (gitignored)
├── spleeter/                # Spleeter library (submodule/clone)
├── requirements.txt         # Python dependencies
├── ARCHITECTURE.md          # Technical documentation
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
| GET | `/crate` | Get all tracks in the crate |
| GET | `/crate/{track_id}` | Get track details with stems |
| DELETE | `/crate/{track_id}` | Delete a track and its stems |
| POST | `/sample` | Create a sample from a stem region |
| GET | `/samples` | Get all samples |
| DELETE | `/samples/{sample_id}` | Delete a sample |
| POST | `/loop` | Create a loop from a stem or sample |
| GET | `/loops` | Get all loops |
| DELETE | `/loops/{loop_id}` | Delete a loop |

## Technologies

- **[FastAPI](https://fastapi.tiangolo.com/)** - Modern Python web framework
- **[Spleeter](https://github.com/deezer/spleeter)** - AI-powered audio source separation by Deezer
- **[WaveSurfer.js](https://wavesurfer.xyz/)** - Interactive waveform visualization
- **[librosa](https://librosa.org/)** - Audio analysis and BPM detection
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** - Download audio from various platforms
- **[Tailwind CSS](https://tailwindcss.com/)** - Utility-first CSS framework

## Documentation

For a deeper dive into the technical implementation, see [ARCHITECTURE.md](ARCHITECTURE.md), which includes:

- System architecture diagrams
- Data flow visualizations
- Database schema (ERD + SQL)
- Complete API endpoint reference
- Frontend state management
- Audio processing pipelines (FFmpeg commands)

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
