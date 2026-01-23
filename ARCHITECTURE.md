# Audio Stem Splitter - Technical Architecture

## System Overview

```
+------------------+     +------------------+     +------------------+
|                  |     |                  |     |                  |
|   Web Browser    |<--->|   FastAPI        |<--->|   SQLite DB      |
|   (Frontend)     |     |   (Backend)      |     |   (spleeter.db)  |
|                  |     |                  |     |                  |
+------------------+     +--------+---------+     +------------------+
                                  |
                                  v
                    +-------------+-------------+
                    |                           |
              +-----v-----+             +-------v-------+
              |           |             |               |
              |  Spleeter |             |    FFmpeg     |
              |   (AI)    |             |   (Audio)     |
              |           |             |               |
              +-----------+             +---------------+
```

---

## Data Flow

### 1. Track Processing Flow

```
                                    +------------------+
                                    |   User Upload    |
                                    |   or URL Fetch   |
                                    +--------+---------+
                                             |
                                             v
+----------------+                  +------------------+
|                |                  |                  |
|  uploads/      |<-----------------+   /upload        |
|  {job_id}/     |   Save original  |   endpoint       |
|  {track}.mp3   |                  |                  |
|                |                  +--------+---------+
+-------+--------+                           |
        |                                    |
        |  Copy to output                    v
        |                           +------------------+
        +-------------------------->|                  |
                                    |  Spleeter AI     |
                                    |  Separation      |
                                    |                  |
                                    +--------+---------+
                                             |
                                             v
                                    +------------------+
                                    |   output/        |
                                    |   {track}/       |
                                    |   - original.mp3 |
                                    |   - vocals.wav   |
                                    |   - drums.wav    |
                                    |   - bass.wav     |
                                    |   - other.wav    |
                                    +--------+---------+
                                             |
                                             v
                                    +------------------+
                                    |   SQLite DB      |
                                    |   - tracks       |
                                    |   - stems        |
                                    +------------------+
```

### 2. Sample Creation Flow

```
+------------------+     +------------------+     +------------------+
|   User selects   |     |   POST /sample   |     |   FFmpeg         |
|   waveform       +---->|                  +---->|   extraction     |
|   region         |     |   track_name     |     |   -ss {start}    |
|   [start, end]   |     |   stem_name      |     |   -t  {duration} |
+------------------+     |   start_time     |     +--------+---------+
                         |   end_time       |              |
                         +------------------+              v
                                                 +------------------+
                                                 |   samples/       |
                                                 |   {track} -      |
                                                 |   {stem}         |
                                                 |   ({s}s-{e}s).wav|
                                                 +--------+---------+
                                                          |
                                                          v
                                                 +------------------+
                                                 |   SQLite DB      |
                                                 |   - samples      |
                                                 +------------------+
```

### 3. Loop Creation Flow

```
+------------------+     +------------------+     +------------------+
|   User selects   |     |   POST /loop     |     |   FFmpeg         |
|   region +       +---->|                  +---->|   1. Extract     |
|   loop count     |     |   source_type    |     |   2. Loop with   |
|   (x2,x4,x8,x16) |     |   track_name     |     |   -stream_loop   |
+------------------+     |   stem_name      |     +--------+---------+
                         |   start_time     |              |
                         |   end_time       |              v
                         |   loop_count     |    +------------------+
                         +------------------+    |   loops/         |
                                                 |   {track} -      |
                                                 |   {stem}         |
                                                 |   ({s}s-{e}s)    |
                                                 |   x{count}.wav   |
                                                 +--------+---------+
                                                          |
                                                          v
                                                 +------------------+
                                                 |   SQLite DB      |
                                                 |   - loops        |
                                                 +------------------+
```

---

## Database Schema

### Entity Relationship Diagram

```
+------------------+       +------------------+
|     tracks       |       |      stems       |
+------------------+       +------------------+
| PK id            |<------| PK id            |
|    name (UNIQUE) |   1:N | FK track_id      |
|    bpm           |       |    name          |
|    duration      |       |    filename      |
|    stem_count    |       |    duration      |
|    original_file |       +------------------+
|    created_at    |
+------------------+
        |
        | (referenced by name)
        |
        v
+------------------+       +------------------+
|     samples      |       |      loops       |
+------------------+       +------------------+
| PK id            |       | PK id            |
|    track_name    |       |    source_type   |
|    stem_name     |       |    track_name    |
|    filename (UQ) |       |    stem_name     |
|    start_time    |       |    filename (UQ) |
|    end_time      |       |    start_time    |
|    duration      |       |    end_time      |
|    created_at    |       |    loop_count    |
+------------------+       |    duration      |
                           |    created_at    |
                           +------------------+
```

### Table Definitions

```sql
-- Processed tracks with metadata
CREATE TABLE tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,        -- Track name (folder name)
    bpm REAL,                         -- Detected tempo
    duration REAL,                    -- Duration in seconds
    stem_count INTEGER,               -- 2, 4, or 5
    original_filename TEXT,           -- e.g., "original.mp3"
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Individual stems for each track
CREATE TABLE stems (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    name TEXT NOT NULL,               -- vocals, drums, bass, etc.
    filename TEXT NOT NULL,           -- vocals.wav
    duration REAL,
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
);

-- Extracted audio samples
CREATE TABLE samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_name TEXT NOT NULL,
    stem_name TEXT NOT NULL,          -- or "original"
    filename TEXT UNIQUE NOT NULL,    -- "{track} - {stem} ({start}s-{end}s).wav"
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    duration REAL NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Looped audio segments
CREATE TABLE loops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_type TEXT NOT NULL,        -- "stem" or "sample"
    track_name TEXT NOT NULL,
    stem_name TEXT NOT NULL,
    filename TEXT UNIQUE NOT NULL,    -- "{track} - {stem} ({s}s-{e}s) x{n}.wav"
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    loop_count INTEGER NOT NULL,      -- 2, 4, 8, 16
    duration REAL NOT NULL,           -- Total looped duration
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## Directory Structure

```
app/
+-- main.py                 # FastAPI application, endpoints, processing
+-- database.py             # SQLite connection, CRUD operations
+-- audio_utils.py          # BPM detection, duration extraction
+-- spleeter.db             # SQLite database file
|
+-- templates/
|   +-- index.html          # Single-page frontend (Tailwind + WaveSurfer.js)
|
+-- uploads/                # Temporary upload storage
|   +-- {job_id}/
|       +-- {original_filename}
|
+-- output/                 # Processed tracks and stems
|   +-- {track_name}/
|       +-- original.mp3    # Original audio file
|       +-- vocals.wav      # Separated stems
|       +-- drums.wav
|       +-- bass.wav
|       +-- piano.wav       # (5-stem only)
|       +-- other.wav
|
+-- samples/                # Extracted audio samples
|   +-- {track} - {stem} ({start}s-{end}s).wav
|
+-- loops/                  # Looped audio segments
    +-- {track} - {stem} ({start}s-{end}s) x{count}.wav
```

---

## API Endpoints

### Track Management

```
GET  /                      Render web interface
GET  /crate                 List all tracks with metadata
GET  /crate/{id}            Get track details with stems
DELETE /crate/{id}          Delete track and all files
```

### Audio Processing

```
POST /analyze               Analyze uploaded file (returns BPM)
     Body: multipart/form-data
     - file: audio file

POST /fetch-url             Download and analyze from URL
     Body: multipart/form-data
     - url: string

POST /upload                Start stem separation job
     Body: multipart/form-data
     - file: audio file (optional)
     - fetched_job_id: string (optional)
     - fetched_audio_path: string (optional)
     - num_stems: 2 | 4 | 5

GET  /status/{job_id}       Poll job status
```

### Samples

```
POST /sample                Create sample from region
     Body: multipart/form-data
     - track_name: string
     - stem_name: string (or "original")
     - start_time: float
     - end_time: float

GET  /samples               List all samples

DELETE /samples/{id}        Delete sample
```

### Loops

```
POST /loop                  Create loop from region
     Body: multipart/form-data
     - source_type: "stem" | "sample"
     - track_name: string
     - stem_name: string (or "original")
     - start_time: float
     - end_time: float
     - loop_count: 2 | 4 | 8 | 16

GET  /loops                 List all loops

DELETE /loops/{id}          Delete loop
```

### Static File Serving

```
GET /output/{track}/{file}      Serve stems and original files
GET /samples-files/{filename}   Serve sample audio files
GET /loops-files/{filename}     Serve loop audio files
```

> Note: Static file routes use `-files` suffix to avoid conflicts with
> API endpoints that need DELETE method support.

---

## Frontend State Management

```
+--------------------+
|   Global State     |
+--------------------+
| crateData[]        |  All tracks from /crate
| samplesData[]      |  All samples from /samples
| loopsData[]        |  All loops from /loops
| expandedTracks{}   |  Track IDs that are expanded
| crateWavesurfers{} |  WaveSurfer instances per track
| sampleWavesurfers{}|  WaveSurfer instances for samples
| loopWavesurfers{}  |  WaveSurfer instances for loops
+--------------------+

Page Load
    |
    v
+------------------+-------------+
    |              |             |
    v              v             v   
loadCrate()  loadSamples()  loadLoops()
    |             |              |
    v             v              v
renderCrate() renderSamples() renderLoops()
```

### WaveSurfer Integration

```
Each audio card:
+------------------------------------------+
|  [Icon] Stem Name           [Sample][DL] |
|  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  |  <- WaveSurfer waveform
|  [>]  0:00 / 3:45                        |     with Regions plugin
+------------------------------------------+

Interaction Modes:
- Normal click:     Seek to position in track
- Shift + drag:     Create selection region for sampling

Region Selection Flow:
1. User holds Shift and drags on waveform
2. Visual preview overlay shows selection in real-time
3. On mouse release, region is created
4. Loop preview popup appears with controls:
   +---------------------------+
   | [Loop] [Stop] | 0:01.234  |  <- Duration display
   +---------------------------+
5. Click loop icon to preview selection on loop
6. Adjust region edges while looping (updates in real-time)
7. Click Sample button to extract, or select loop count for loops
8. Press Esc to clear selection and stop loop preview
```

---

## Startup Migration Sequence

```
startup()
    |
    v
init_db()
    |  Create tables if not exist
    |  Add original_filename column if missing
    v
migrate_originals_from_uploads()
    |  Scan uploads/{job_id}/ folders
    |  Copy {track}.mp3 -> output/{track}/original.mp3
    v
migrate_existing_tracks()
    |  Scan output/ folders
    |  Create/update track records
    |  Link original files to tracks
    v
migrate_existing_samples()
    |  Scan samples/ folder
    |  Parse filenames for metadata
    |  Create sample records
    v
migrate_existing_loops()
       Scan loops/ folder
       Parse filenames for metadata
       Create loop records
```

---

## Audio Processing Pipeline

### Stem Separation (Spleeter)

```
Input: audio file (any format)
                |
                v
        +-------+-------+
        |   Spleeter    |
        |   AI Model    |
        +-------+-------+
                |
    +-----------+-----------+
    |     |     |     |     |
    v     v     v     v     v
 vocals drums bass piano other
  .wav   .wav  .wav  .wav  .wav
```

### Sample Extraction (FFmpeg)

```
ffmpeg -y -i {source} -ss {start} -t {duration} -c copy {output}

-y          Overwrite output
-i          Input file
-ss         Start time (seconds)
-t          Duration (seconds)
-c copy     Stream copy (no re-encoding)
```

### Loop Creation (FFmpeg)

```
Step 1: Extract segment
ffmpeg -y -i {source} -ss {start} -t {duration} -c copy {temp}

Step 2: Loop segment
ffmpeg -y -stream_loop {N-1} -i {temp} -c copy {output}

-stream_loop N   Repeat input N additional times (total N+1)
```

---

## Technologies

| Component | Technology |
|-----------|------------|
| Backend | FastAPI (Python) |
| Database | SQLite3 |
| AI Model | Spleeter (TensorFlow) |
| Audio Processing | FFmpeg, librosa, soundfile |
| Frontend | Vanilla JS, Tailwind CSS |
| Waveforms | WaveSurfer.js v7 |
| URL Downloads | yt-dlp |
