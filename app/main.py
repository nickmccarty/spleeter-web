import os
import sys
import uuid
import shutil
import asyncio
import tempfile
import subprocess
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

# Local imports for database and audio utilities
# Add app directory to path for local imports
APP_DIR = Path(__file__).parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from database import (
    init_db, create_track, create_stem, get_all_tracks,
    get_track_with_stems, track_exists, delete_track, get_track_by_name,
    update_track_original,
    create_sample, get_all_samples, get_sample_by_id, delete_sample, sample_exists,
    create_loop, get_all_loops, get_loop_by_id, delete_loop, loop_exists
)
from audio_utils import get_audio_duration, analyze_track

app = FastAPI(title="Audio Stem Splitter", description="Split audio into stems using Spleeter")

# Directories
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
STATIC_DIR = BASE_DIR / "static"
TEMPLATES_DIR = BASE_DIR / "templates"
SAMPLES_DIR = BASE_DIR / "samples"
LOOPS_DIR = BASE_DIR / "loops"

# Create directories
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
STATIC_DIR.mkdir(exist_ok=True)
SAMPLES_DIR.mkdir(exist_ok=True)
LOOPS_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")
app.mount("/samples-files", StaticFiles(directory=str(SAMPLES_DIR)), name="samples")
app.mount("/loops-files", StaticFiles(directory=str(LOOPS_DIR)), name="loops")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Store job status
jobs = {}


@app.on_event("startup")
async def startup():
    """Initialize database and migrate existing tracks, samples, and loops."""
    init_db()
    await migrate_originals_from_uploads()
    await migrate_existing_tracks()
    await migrate_existing_samples()
    await migrate_existing_loops()


async def migrate_originals_from_uploads():
    """Copy original files from uploads folder to output folders."""
    if not UPLOAD_DIR.exists() or not OUTPUT_DIR.exists():
        return

    for job_dir in UPLOAD_DIR.iterdir():
        if not job_dir.is_dir():
            continue

        # Find audio files in this job directory
        for audio_file in job_dir.iterdir():
            if audio_file.suffix.lower() in ['.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac']:
                # The audio file's stem (name without extension) should match an output folder
                track_name = audio_file.stem
                output_track_dir = OUTPUT_DIR / track_name

                if output_track_dir.exists():
                    # Check if original already exists in output
                    original_dest = output_track_dir / f"original{audio_file.suffix}"
                    if not original_dest.exists():
                        try:
                            shutil.copy2(str(audio_file), str(original_dest))
                            print(f"Copied original for: {track_name}")
                        except Exception as e:
                            print(f"Failed to copy original for {track_name}: {e}")


async def migrate_existing_tracks():
    """Scan output folder and populate DB for tracks not yet in database."""
    if not OUTPUT_DIR.exists():
        return

    for track_dir in OUTPUT_DIR.iterdir():
        if track_dir.is_dir():
            # Check for original file (could be original.mp3, original.wav, etc.)
            original_file = None
            for ext in ['.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac']:
                candidate = track_dir / f"original{ext}"
                if candidate.exists():
                    original_file = candidate
                    break

            # Check if track already exists in DB
            existing_track = get_track_by_name(track_dir.name)
            if existing_track:
                # Update original_filename if we found one and it's not set
                if original_file and not existing_track.get('original_filename'):
                    update_track_original(existing_track['id'], original_file.name)
                    print(f"Updated original for: {track_dir.name}")
                continue

            # Find WAV stems (excluding original files)
            all_wav = list(track_dir.glob("*.wav"))
            stems = [s for s in all_wav if not s.stem.startswith("original")]
            if not stems:
                continue

            # Analyze first available stem (prefer vocals for BPM accuracy)
            vocals_path = track_dir / "vocals.wav"
            analyze_path = vocals_path if vocals_path.exists() else stems[0]

            try:
                # Run analysis in thread pool
                loop = asyncio.get_event_loop()
                analysis = await loop.run_in_executor(
                    None, analyze_track, str(analyze_path)
                )

                # Create track record
                track_id = create_track(
                    name=track_dir.name,
                    bpm=analysis["bpm"],
                    duration=analysis["duration"],
                    stem_count=len(stems),
                    original_filename=original_file.name if original_file else None
                )

                # Create stem records
                for stem_path in stems:
                    stem_duration = await loop.run_in_executor(
                        None, get_audio_duration, str(stem_path)
                    )
                    create_stem(
                        track_id=track_id,
                        name=stem_path.stem,
                        filename=stem_path.name,
                        duration=stem_duration
                    )

                print(f"Migrated track: {track_dir.name}")

            except Exception as e:
                print(f"Failed to migrate {track_dir.name}: {e}")


async def migrate_existing_samples():
    """Scan samples folder and populate DB for samples not yet in database."""
    import re

    if not SAMPLES_DIR.exists():
        return

    # Pattern: "Track Name - stem_name (start_times-end_times).wav"
    pattern = re.compile(r'^(.+) - (\w+) \((\d+\.?\d*)s-(\d+\.?\d*)s\)\.wav$')

    for sample_file in SAMPLES_DIR.iterdir():
        if sample_file.is_file() and sample_file.suffix == '.wav':
            filename = sample_file.name

            if sample_exists(filename):
                continue

            match = pattern.match(filename)
            if not match:
                print(f"Skipping sample with unrecognized format: {filename}")
                continue

            try:
                track_name = match.group(1)
                stem_name = match.group(2)
                start_time = float(match.group(3))
                end_time = float(match.group(4))
                duration = end_time - start_time

                create_sample(
                    track_name=track_name,
                    stem_name=stem_name,
                    filename=filename,
                    start_time=start_time,
                    end_time=end_time,
                    duration=duration
                )

                print(f"Migrated sample: {filename}")

            except Exception as e:
                print(f"Failed to migrate sample {filename}: {e}")


async def migrate_existing_loops():
    """Scan loops folder and populate DB for loops not yet in database."""
    import re

    if not LOOPS_DIR.exists():
        return

    # Pattern: "Track Name - stem_name (start_times-end_times) xN.wav"
    pattern = re.compile(r'^(.+) - (\w+) \((\d+\.?\d*)s-(\d+\.?\d*)s\) x(\d+)\.wav$')

    for loop_file in LOOPS_DIR.iterdir():
        if loop_file.is_file() and loop_file.suffix == '.wav':
            filename = loop_file.name

            if loop_exists(filename):
                continue

            match = pattern.match(filename)
            if not match:
                print(f"Skipping loop with unrecognized format: {filename}")
                continue

            try:
                track_name = match.group(1)
                stem_name = match.group(2)
                start_time = float(match.group(3))
                end_time = float(match.group(4))
                loop_count = int(match.group(5))
                segment_duration = end_time - start_time
                total_duration = segment_duration * loop_count

                create_loop(
                    source_type="stem",  # Assume stem for migrated loops
                    track_name=track_name,
                    stem_name=stem_name,
                    filename=filename,
                    start_time=start_time,
                    end_time=end_time,
                    loop_count=loop_count,
                    duration=total_duration
                )

                print(f"Migrated loop: {filename}")

            except Exception as e:
                print(f"Failed to migrate loop {filename}: {e}")


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

        # Copy original file to output directory
        original_filename = f"original{audio_path.suffix}"
        original_dest = stem_dir / original_filename
        try:
            shutil.copy2(str(audio_path), str(original_dest))
        except Exception as copy_error:
            print(f"Failed to copy original file: {copy_error}")
            original_filename = None

        # Save to database if not already exists
        if not track_exists(audio_name):
            try:
                # Analyze first stem for metadata
                vocals_path = stem_dir / "vocals.wav"
                analyze_path = vocals_path if vocals_path.exists() else next(stem_dir.glob("*.wav"))

                analysis = await loop.run_in_executor(
                    None, analyze_track, str(analyze_path)
                )

                # Create track record
                track_id = create_track(
                    name=audio_name,
                    bpm=analysis["bpm"],
                    duration=analysis["duration"],
                    stem_count=num_stems,
                    original_filename=original_filename
                )

                # Create stem records
                for stem_name in stem_names:
                    stem_file = stem_dir / f"{stem_name}.wav"
                    if stem_file.exists():
                        stem_duration = await loop.run_in_executor(
                            None, get_audio_duration, str(stem_file)
                        )
                        create_stem(
                            track_id=track_id,
                            name=stem_name,
                            filename=f"{stem_name}.wav",
                            duration=stem_duration
                        )
            except Exception as db_error:
                print(f"Failed to save to database: {db_error}")

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


@app.get("/crate")
async def get_crate():
    """Get all tracks in the crate."""
    tracks = get_all_tracks()
    has_output = OUTPUT_DIR.exists() and any(OUTPUT_DIR.iterdir())
    return JSONResponse({"tracks": tracks, "has_output": has_output})


@app.get("/crate/{track_id}")
async def get_crate_track(track_id: int):
    """Get track details with stems."""
    track = get_track_with_stems(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")
    return JSONResponse(track)


@app.delete("/crate/{track_id}")
async def delete_crate_track(track_id: int):
    """Delete a track from the crate and remove its files."""
    track = get_track_with_stems(track_id)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    # Delete output directory
    track_output_dir = OUTPUT_DIR / track["name"]
    if track_output_dir.exists():
        shutil.rmtree(track_output_dir)

    # Delete from database
    delete_track(track_id)

    return JSONResponse({"status": "deleted", "name": track["name"]})


@app.post("/sample")
async def create_sample_endpoint(
    track_name: str = Form(...),
    stem_name: str = Form(...),
    start_time: float = Form(...),
    end_time: float = Form(...)
):
    """Extract a sample from a stem between start and end times."""
    # Validate input
    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="Start time must be before end time")

    if start_time < 0:
        raise HTTPException(status_code=400, detail="Start time cannot be negative")

    # Find the source stem file
    if stem_name == "original":
        # Original file could have various extensions
        stem_file = None
        for ext in ['.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac']:
            candidate = OUTPUT_DIR / track_name / f"original{ext}"
            if candidate.exists():
                stem_file = candidate
                break
        if not stem_file:
            raise HTTPException(status_code=404, detail="Original file not found")
    else:
        stem_file = OUTPUT_DIR / track_name / f"{stem_name}.wav"
        if not stem_file.exists():
            raise HTTPException(status_code=404, detail="Stem file not found")

    # Create sample filename with timestamps
    duration = end_time - start_time
    sample_name = f"{track_name} - {stem_name} ({start_time:.2f}s-{end_time:.2f}s).wav"
    sample_path = SAMPLES_DIR / sample_name

    # Use ffmpeg to extract the segment
    try:
        cmd = [
            "ffmpeg", "-y",  # Overwrite if exists
            "-i", str(stem_file),
            "-ss", str(start_time),
            "-t", str(duration),
            "-c", "copy",  # Copy codec (no re-encoding for speed)
            str(sample_path)
        ]

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(cmd, capture_output=True, check=True)
        )

        # Save to database
        sample_id = create_sample(
            track_name=track_name,
            stem_name=stem_name,
            filename=sample_name,
            start_time=start_time,
            end_time=end_time,
            duration=duration
        )

        return JSONResponse({
            "status": "created",
            "sample_id": sample_id,
            "sample_url": f"/samples-files/{sample_name}",
            "sample_name": sample_name,
            "duration": duration
        })

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to extract sample: {e.stderr.decode() if e.stderr else str(e)}"
        )


@app.get("/samples")
async def list_samples():
    """Get all samples."""
    samples = get_all_samples()
    has_samples = SAMPLES_DIR.exists() and any(SAMPLES_DIR.iterdir())
    return JSONResponse({"samples": samples, "has_samples": has_samples})


@app.delete("/samples/{sample_id}")
async def delete_sample_endpoint(sample_id: int):
    """Delete a sample."""
    sample = get_sample_by_id(sample_id)
    if not sample:
        raise HTTPException(status_code=404, detail="Sample not found")

    # Delete file
    sample_path = SAMPLES_DIR / sample["filename"]
    if sample_path.exists():
        sample_path.unlink()

    # Delete from database
    delete_sample(sample_id)

    return JSONResponse({"status": "deleted", "filename": sample["filename"]})


@app.post("/loop")
async def create_loop_endpoint(
    source_type: str = Form(...),
    track_name: str = Form(...),
    stem_name: str = Form(...),
    start_time: float = Form(...),
    end_time: float = Form(...),
    loop_count: int = Form(...)
):
    """Create a loop from a stem or sample segment."""
    # Validate input
    if start_time >= end_time:
        raise HTTPException(status_code=400, detail="Start time must be before end time")

    if start_time < 0:
        raise HTTPException(status_code=400, detail="Start time cannot be negative")

    if loop_count < 2:
        raise HTTPException(status_code=400, detail="Loop count must be at least 2")

    # Find the source file
    if source_type == "stem":
        if stem_name == "original":
            # Original file could have various extensions
            source_file = None
            for ext in ['.mp3', '.wav', '.flac', '.m4a', '.ogg', '.aac']:
                candidate = OUTPUT_DIR / track_name / f"original{ext}"
                if candidate.exists():
                    source_file = candidate
                    break
            if not source_file:
                raise HTTPException(status_code=404, detail="Original file not found")
        else:
            source_file = OUTPUT_DIR / track_name / f"{stem_name}.wav"
    elif source_type == "sample":
        # For samples, we need to find the sample file
        # The sample filename pattern is: "Track - stem (start-end).wav"
        sample_filename = f"{track_name} - {stem_name} ({start_time:.2f}s-{end_time:.2f}s).wav"
        source_file = SAMPLES_DIR / sample_filename
    else:
        raise HTTPException(status_code=400, detail="Invalid source type")

    if not source_file.exists():
        raise HTTPException(status_code=404, detail="Source file not found")

    # Create loop filename
    segment_duration = end_time - start_time
    total_duration = segment_duration * loop_count
    loop_name = f"{track_name} - {stem_name} ({start_time:.2f}s-{end_time:.2f}s) x{loop_count}.wav"
    loop_path = LOOPS_DIR / loop_name

    # Use ffmpeg to create the loop
    # First extract segment, then loop it
    try:
        import tempfile

        # Create a temporary file for the segment
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
            tmp_path = tmp.name

        # Extract the segment
        extract_cmd = [
            "ffmpeg", "-y",
            "-i", str(source_file),
            "-ss", str(start_time),
            "-t", str(segment_duration),
            "-c", "copy",
            tmp_path
        ]

        # Loop the segment using stream_loop
        # -stream_loop N means repeat N more times (so total is N+1)
        loop_cmd = [
            "ffmpeg", "-y",
            "-stream_loop", str(loop_count - 1),
            "-i", tmp_path,
            "-c", "copy",
            str(loop_path)
        ]

        event_loop = asyncio.get_event_loop()

        # Run extraction
        await event_loop.run_in_executor(
            None,
            lambda: subprocess.run(extract_cmd, capture_output=True, check=True)
        )

        # Run looping
        await event_loop.run_in_executor(
            None,
            lambda: subprocess.run(loop_cmd, capture_output=True, check=True)
        )

        # Clean up temp file
        os.unlink(tmp_path)

        # Save to database
        loop_id = create_loop(
            source_type=source_type,
            track_name=track_name,
            stem_name=stem_name,
            filename=loop_name,
            start_time=start_time,
            end_time=end_time,
            loop_count=loop_count,
            duration=total_duration
        )

        return JSONResponse({
            "status": "created",
            "loop_id": loop_id,
            "loop_url": f"/loops-files/{loop_name}",
            "loop_name": loop_name,
            "duration": total_duration
        })

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create loop: {e.stderr.decode() if e.stderr else str(e)}"
        )


@app.get("/loops")
async def list_loops():
    """Get all loops."""
    loops = get_all_loops()
    has_loops = LOOPS_DIR.exists() and any(LOOPS_DIR.iterdir())
    return JSONResponse({"loops": loops, "has_loops": has_loops})


@app.delete("/loops/{loop_id}")
async def delete_loop_endpoint(loop_id: int):
    """Delete a loop."""
    loop = get_loop_by_id(loop_id)
    if not loop:
        raise HTTPException(status_code=404, detail="Loop not found")

    # Delete file
    loop_path = LOOPS_DIR / loop["filename"]
    if loop_path.exists():
        loop_path.unlink()

    # Delete from database
    delete_loop(loop_id)

    return JSONResponse({"status": "deleted", "filename": loop["filename"]})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
