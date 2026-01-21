import os
import sys
import uuid
import shutil
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import JSONResponse
import aiofiles
import yt_dlp
import librosa

# Add spleeter to path
SPLEETER_PATH = Path(__file__).parent.parent / "spleeter"
sys.path.insert(0, str(SPLEETER_PATH))

from spleeter.separator import Separator

app = FastAPI(title="Audio Stem Splitter", description="Split audio into stems using Spleeter")

# Directories
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"

# Create directories
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Store job status
jobs = {}


def get_stem_names(num_stems: int) -> list[str]:
    """Return stem names based on the number of stems."""
    if num_stems == 2:
        return ["vocals", "accompaniment"]
    elif num_stems == 4:
        return ["vocals", "drums", "bass", "other"]
    elif num_stems == 5:
        return ["vocals", "drums", "bass", "piano", "other"]
    else:
        raise ValueError(f"Invalid number of stems: {num_stems}")


def analyze_audio_file(file_path: str) -> dict:
    """Analyze audio file to extract BPM."""
    # Load audio with librosa
    y, sr = librosa.load(file_path, sr=None)

    # Calculate BPM
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo = librosa.beat.tempo(onset_envelope=onset_env, sr=sr)[0]

    return {
        "bpm": float(tempo)
    }


async def download_audio_from_url(url: str, output_path: Path) -> dict:
    """Download audio from URL using yt-dlp. Returns dict with path and metadata."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': str(output_path / '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    loop = asyncio.get_event_loop()

    def download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # Get the actual filename
            if 'entries' in info:
                info = info['entries'][0]
            filename = ydl.prepare_filename(info)
            # Replace extension with mp3
            mp3_path = Path(filename).with_suffix('.mp3')

            return {
                'audio_path': mp3_path,
                'title': info.get('title', ''),
                'artist': info.get('artist') or info.get('uploader') or info.get('channel', ''),
                'thumbnail': info.get('thumbnail', '')
            }

    return await loop.run_in_executor(None, download)


def run_separation(audio_path: Path, output_dir: Path, num_stems: int) -> None:
    """Run spleeter separation (blocking, runs in thread pool)."""
    stem_config = f"spleeter:{num_stems}stems"
    separator = Separator(stem_config)
    separator.separate_to_file(str(audio_path), str(output_dir))


async def separate_audio(audio_path: Path, output_dir: Path, num_stems: int, job_id: str):
    """Separate audio using Spleeter."""
    try:
        jobs[job_id]["status"] = "processing"
        jobs[job_id]["message"] = "Separating audio into stems..."

        # Run spleeter in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, run_separation, audio_path, output_dir, num_stems)

        # Find output files
        audio_name = audio_path.stem
        stem_dir = output_dir / audio_name

        if not stem_dir.exists():
            jobs[job_id]["status"] = "error"
            jobs[job_id]["message"] = "Output directory not found"
            return

        stem_names = get_stem_names(num_stems)
        stems = {}

        for stem_name in stem_names:
            stem_file = stem_dir / f"{stem_name}.wav"
            if stem_file.exists():
                # Create relative URL for frontend
                stems[stem_name] = f"/output/{audio_name}/{stem_name}.wav"

        jobs[job_id]["status"] = "completed"
        jobs[job_id]["message"] = "Audio separation complete!"
        jobs[job_id]["stems"] = stems
        jobs[job_id]["audio_name"] = audio_name

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["message"] = str(e)


@app.get("/")
async def index(request: Request):
    """Render the main page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/analyze")
async def analyze_audio(file: UploadFile = File(...)):
    """Analyze uploaded audio file to get BPM and spectrogram."""
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Run analysis in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, analyze_audio_file, tmp_path)
        return JSONResponse(result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up temp file
        os.unlink(tmp_path)


@app.post("/fetch-url")
async def fetch_and_analyze_url(url: str = Form(...)):
    """Download audio from URL and analyze it."""
    job_id = str(uuid.uuid4())
    job_upload_dir = UPLOAD_DIR / job_id
    job_upload_dir.mkdir(exist_ok=True)

    try:
        # Download audio (returns dict with path and metadata)
        download_result = await download_audio_from_url(url, job_upload_dir)
        audio_path = download_result['audio_path']

        # Analyze the downloaded file
        loop = asyncio.get_event_loop()
        analysis = await loop.run_in_executor(None, analyze_audio_file, str(audio_path))

        # Return analysis plus file info for later use
        return JSONResponse({
            "job_id": job_id,
            "audio_path": str(audio_path),
            "audio_url": f"/uploads/{job_id}/{audio_path.name}",
            "filename": audio_path.name,
            "title": download_result['title'],
            "artist": download_result['artist'],
            "thumbnail": download_result['thumbnail'],
            "bpm": analysis["bpm"]
        })
    except Exception as e:
        # Clean up on error
        if job_upload_dir.exists():
            shutil.rmtree(job_upload_dir)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload_audio(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = File(None),
    url: Optional[str] = Form(None),
    fetched_job_id: Optional[str] = Form(None),
    fetched_audio_path: Optional[str] = Form(None),
    num_stems: int = Form(2)
):
    """Upload audio file or provide URL for stem separation."""
    if not file and not url and not fetched_audio_path:
        raise HTTPException(status_code=400, detail="Please provide a file, URL, or pre-fetched audio")

    if num_stems not in [2, 4, 5]:
        raise HTTPException(status_code=400, detail="Number of stems must be 2, 4, or 5")

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "message": "Initializing...",
        "stems": {},
        "audio_name": ""
    }

    try:
        if file and file.filename:
            # Handle file upload
            jobs[job_id]["message"] = "Uploading file..."

            # Create job-specific upload directory
            job_upload_dir = UPLOAD_DIR / job_id
            job_upload_dir.mkdir(exist_ok=True)

            file_path = job_upload_dir / file.filename

            async with aiofiles.open(file_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)

            audio_path = file_path

        elif fetched_audio_path:
            # Handle pre-fetched audio from URL (already downloaded via /fetch-url)
            jobs[job_id]["message"] = "Using pre-fetched audio..."
            audio_path = Path(fetched_audio_path)

            if not audio_path.exists():
                raise HTTPException(status_code=400, detail="Pre-fetched audio file not found")

        elif url:
            # Handle URL download (fallback, shouldn't normally be used with new flow)
            jobs[job_id]["message"] = "Downloading audio from URL..."

            job_upload_dir = UPLOAD_DIR / job_id
            job_upload_dir.mkdir(exist_ok=True)

            download_result = await download_audio_from_url(url, job_upload_dir)
            audio_path = download_result['audio_path']

        # Create job-specific output directory
        job_output_dir = OUTPUT_DIR

        # Start separation in background
        background_tasks.add_task(separate_audio, audio_path, job_output_dir, num_stems, job_id)

        return JSONResponse({"job_id": job_id, "status": "started"})

    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["message"] = str(e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a separation job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return JSONResponse(jobs[job_id])


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Clean up job files."""
    if job_id in jobs:
        # Clean up upload directory
        job_upload_dir = UPLOAD_DIR / job_id
        if job_upload_dir.exists():
            shutil.rmtree(job_upload_dir)

        # Clean up output directory if we have an audio name
        if jobs[job_id].get("audio_name"):
            job_output_dir = OUTPUT_DIR / jobs[job_id]["audio_name"]
            if job_output_dir.exists():
                shutil.rmtree(job_output_dir)

        del jobs[job_id]

    return JSONResponse({"status": "deleted"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
