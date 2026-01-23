# Audio Stem Splitter - Codebase Reference

> A detailed technical reference for future development sessions. This document maps HTML components to their JavaScript functions and CSS styling.

---

## Table of Contents

1. [File Overview](#file-overview)
2. [HTML Structure](#html-structure)
3. [CSS Classes](#css-classes)
4. [JavaScript State](#javascript-state)
5. [JavaScript Functions](#javascript-functions)
6. [Component Reference](#component-reference)
7. [API Endpoints](#api-endpoints)
8. [Database Functions](#database-functions)

---

## File Overview

| File | Purpose | Lines |
|------|---------|-------|
| `app/templates/index.html` | Single-page frontend (HTML + JS + CSS) | ~2300 |
| `app/main.py` | FastAPI backend, endpoints, processing | ~900 |
| `app/database.py` | SQLite CRUD operations | ~350 |
| `app/audio_utils.py` | BPM detection, duration extraction | ~50 |

---

## HTML Structure

### Main Sections (in DOM order)

```
body.gradient-bg
└── div.container (max-w-4xl)
    ├── header                          # App title
    ├── #upload-section                 # File/URL input, preview, stem selection
    ├── #status-section                 # Processing spinner (hidden by default)
    ├── #results-section                # Separated stems display (hidden by default)
    ├── #error-section                  # Error display (hidden by default)
    ├── #crate-section                  # Track library (hidden by default)
    ├── #samples-section                # Extracted samples (hidden by default)
    ├── #loops-section                  # Created loops (hidden by default)
    └── footer                          # Spleeter credit
```

### Section Details

#### Upload Section (`#upload-section`)
```
#upload-section.glass
├── #upload-form
│   ├── Tab buttons (#tab-file, #tab-url)
│   ├── #file-section
│   │   └── #upload-zone (drag & drop)
│   │       └── #file-input (hidden)
│   ├── #url-section.hidden
│   │   ├── #url-input
│   │   └── #fetch-url-btn
│   ├── #preview-section.hidden
│   │   ├── #track-info.hidden (cover art, title, artist)
│   │   ├── #waveform (WaveSurfer container)
│   │   ├── #waveform-loading (shimmer placeholder)
│   │   ├── Playback controls (#play-btn, #current-time, #duration)
│   │   └── #bpm-display
│   ├── Stem selection (radio buttons: 2, 4, 5)
│   └── #submit-btn
```

#### Status Section (`#status-section`)
```
#status-section.glass.hidden
├── .spinner
├── #status-title
└── #status-message
```

#### Results Section (`#results-section`)
```
#results-section.hidden
├── Header with "Split Another" button
└── #stems-grid
    └── .stem-card (generated for each stem)
```

#### Crate Section (`#crate-section`)
```
#crate-section.glass.hidden
├── Header with #crate-count
└── #crate-list
    └── .crate-row (generated)
        ├── .crate-row-header (clickable)
        └── #crate-stems-{trackId}.hidden
            └── .stem-card (generated on expand)
```

#### Samples Section (`#samples-section`)
```
#samples-section.glass.hidden
├── Header with #samples-count
└── #samples-list
    └── .stem-card (generated)
```

#### Loops Section (`#loops-section`)
```
#loops-section.glass.hidden
├── Header with #loops-count
└── #loops-list
    └── .stem-card (generated)
```

---

## CSS Classes

### Custom Classes (defined in `<style>`)

| Class | Purpose | Properties |
|-------|---------|------------|
| `.gradient-bg` | Page background | `linear-gradient(135deg, #1a1a2e, #16213e, #0f3460)` |
| `.glass` | Glassmorphism cards | `rgba(255,255,255,0.05)`, `backdrop-filter: blur(10px)`, border |
| `.stem-card` | Audio card styling | Gradient background, hover border effect |
| `.upload-zone` | Drag & drop area | Dashed indigo border, hover/drag-over states |
| `.pulse-animation` | Pulsing opacity | Keyframe animation 50% opacity |
| `.spinner` | Loading spinner | Border animation, 40x40px |
| `.stem-icon` | Icon container | 48x48px, rounded, centered |
| `.spectrogram-loading` | Shimmer placeholder | Animated gradient background |
| `.crate-chevron` | Expand/collapse arrow | `transition: transform 0.2s` |
| `.crate-row-header:hover` | Row hover state | `background: rgba(255,255,255,0.08)` |

### Tailwind Patterns Used

| Pattern | Usage |
|---------|-------|
| `bg-{color}-500/20` | Semi-transparent backgrounds for icons |
| `text-{color}-400` | Colored text (pink, orange, green, etc.) |
| `hover:bg-white/10` | Subtle hover states |
| `peer-checked:border-indigo-500` | Selected stem count styling |
| `rounded-xl`, `rounded-2xl` | Card border radius |
| `focus:ring-2 focus:ring-indigo-500/20` | Focus states |
| `transition-all transform hover:scale-[1.02]` | Button hover effects |

### Stem Color Mapping

```javascript
const stemIcons = {
    vocals:        { emoji: '🎤', color: 'bg-pink-500/20',   text: 'text-pink-400'   },
    accompaniment: { emoji: '🎵', color: 'bg-blue-500/20',   text: 'text-blue-400'   },
    drums:         { emoji: '🥁', color: 'bg-orange-500/20', text: 'text-orange-400' },
    bass:          { emoji: '🎸', color: 'bg-green-500/20',  text: 'text-green-400'  },
    piano:         { emoji: '🎹', color: 'bg-purple-500/20', text: 'text-purple-400' },
    other:         { emoji: '🎼', color: 'bg-yellow-500/20', text: 'text-yellow-400' },
    original:      { emoji: '💿', color: 'bg-cyan-500/20',   text: 'text-cyan-400'   }  // Added in loadTrackStems
};
```

---

## JavaScript State

### Global Variables (lines 362-391)

```javascript
// Tab & Job State
let currentTab = 'file';           // 'file' | 'url'
let currentJobId = null;           // UUID of current processing job
let pollInterval = null;           // setInterval ID for status polling
let previewReady = false;          // Whether audio preview is loaded
let urlFetchData = null;           // Data from /fetch-url response

// WaveSurfer Instances
let wavesurfer = null;             // Preview waveform
let stemWavesurfers = [];          // Results section stems

// Crate State
let crateData = [];                // Array of track objects from /crate
let expandedTracks = {};           // { trackId: true } for expanded rows
let crateWavesurfers = {};         // { trackId: [WaveSurfer, ...] }

// Samples State
let samplesData = [];              // Array of sample objects from /samples
let sampleWavesurfers = {};        // { sampleId: WaveSurfer }

// Loops State
let loopsData = [];                // Array of loop objects from /loops
let loopWavesurfers = {};          // { loopId: WaveSurfer }

// Region Selection State
let activeRegions = {};            // { uniqueId: RegionObject }

// Loop Preview State
let loopPreviewState = {
    isLooping: false,              // Whether loop preview is active
    currentId: null,               // uniqueId of looping region
    wavesurfer: null               // WaveSurfer instance being looped
};
```

---

## JavaScript Functions

### Core UI Functions

| Function | Line | Purpose |
|----------|------|---------|
| `switchTab(tab)` | 1807 | Toggle between file/URL tabs |
| `resetForm()` | 2283 | Reset UI to initial state |
| `showError(message)` | 2277 | Display error section |
| `formatTime(seconds)` | 1927 | Format as `M:SS` |
| `formatTimePrecise(seconds)` | 1934 | Format as `M:SS.mmm` |
| `parseTimePrecise(timeStr)` | 1942 | Parse `M:SS.mmm` to seconds |

### Upload & Processing Functions

| Function | Line | Purpose |
|----------|------|---------|
| `showFilePreview(file)` | 1952 | Load file into WaveSurfer, get BPM |
| `fetchFromUrl()` | 1993 | Call `/fetch-url`, show preview |
| `initWaveSurfer()` | 1874 | Create WaveSurfer for preview |
| `startPolling()` | 2119 | Poll `/status/{job_id}` until complete |
| `showResults(data)` | 2141 | Render separated stems |

### Crate Functions

| Function | Line | Purpose |
|----------|------|---------|
| `loadCrate()` | 804 | Fetch `/crate`, call renderCrate |
| `renderCrate()` | 819 | Build crate row HTML |
| `toggleCrateRow(trackId, headerEl)` | 872 | Expand/collapse track row |
| `loadTrackStems(trackId)` | 893 | Fetch `/crate/{id}`, render stems with WaveSurfer |
| `deleteTrack(trackId, trackName)` | 1364 | DELETE `/crate/{id}`, refresh |

### Sample Functions

| Function | Line | Purpose |
|----------|------|---------|
| `loadSamples()` | 1398 | Fetch `/samples`, call renderSamples |
| `renderSamples()` | 1415 | Build sample card HTML with WaveSurfer |
| `deleteSample(sampleId, filename)` | 1571 | DELETE `/samples/{id}`, refresh |

### Loop Functions

| Function | Line | Purpose |
|----------|------|---------|
| `loadLoops()` | 1604 | Fetch `/loops`, call renderLoops |
| `renderLoops()` | 1621 | Build loop card HTML with WaveSurfer |
| `deleteLoop(loopId, filename)` | 1737 | DELETE `/loops/{id}`, refresh |
| `createLoop(...)` | 1769 | POST `/loop`, refresh loops list |

### Region Selection Functions

| Function | Line | Scope | Purpose |
|----------|------|-------|---------|
| `setupRegionSelection(uniqueId, wavesurfer, regions, onRegionCreated, onRegionUpdated)` | 432 | Global | Wire up shift+drag region selection |
| `createPreviewOverlay()` | 441 | Inner | Create green overlay during drag |
| `createLoopPopup()` | 451 | Inner | Create popup with time inputs, loop controls |
| `updateRegionFromInputs()` | 529 | Inner | Sync region from input fields |
| `updateInputsFromRegion()` | 544 | Inner | Sync input fields from region |
| `adjustTime(isStart, delta)` | 552 | Inner | Increment/decrement time by 10ms |
| `startLoopPreview()` | 615 | Inner | Begin looping playback |
| `updatePopupPosition()` | 661 | Inner | Position popup above region |
| `stopLoopPreview()` | 394 | Global | Stop loop preview, reset UI |

### Utility Functions

| Function | Line | Purpose |
|----------|------|---------|
| `getComputedColor(textClass)` | 2245 | Extract hex color from Tailwind class |
| `adjustColor(hex, factor)` | 2258 | Lighten/darken hex color |
| `getStemDescription(name)` | 2265 | Get human-readable stem description |

---

## Component Reference

### Stem Card (in Crate/Results)

**HTML Structure:**
```html
<div class="stem-card rounded-xl p-4">
    <div class="flex items-center justify-between mb-3">
        <div class="flex items-center space-x-3">
            <div class="stem-icon {color}">{emoji}</div>
            <span class="font-medium {text}">{name}</span>
        </div>
        <div class="flex items-center space-x-2">
            <button id="sample-btn-{id}" class="hidden ...">Sample</button>
            <div id="loop-controls-{id}" class="hidden ...">
                <select id="stem-loop-count-{id}">x2, x4, x8, x16</select>
                <button id="stem-loop-btn-{id}">✓</button>
            </div>
            <a href="..." download>Download</a>
        </div>
    </div>
    <div class="relative">
        <div id="waveform-{id}" class="w-full h-16"></div>
        <!-- Loop popup inserted here dynamically -->
    </div>
    <div class="flex items-center justify-between mt-3">
        <button id="play-btn-{id}">Play/Pause</button>
        <div class="font-mono">
            <span id="time-{id}">0:00</span> / <span id="duration-{id}">0:00</span>
        </div>
    </div>
</div>
```

**Driven by:**
- `loadTrackStems()` - Creates cards for crate stems
- `showResults()` - Creates cards for results stems
- `renderSamples()` - Creates cards for samples
- `renderLoops()` - Creates cards for loops

**WaveSurfer Setup:**
```javascript
const ws = WaveSurfer.create({
    container: `#waveform-${uniqueId}`,
    waveColor: getComputedColor(icon.text),
    progressColor: adjustColor(getComputedColor(icon.text), 1.3),
    cursorColor: '#ffffff',
    barWidth: 2,
    barGap: 1,
    barRadius: 2,
    height: 64,
    normalize: true
});

const regions = ws.registerPlugin(WaveSurfer.Regions.create());
setupRegionSelection(uniqueId, ws, regions, onRegionCreated, onRegionUpdated);
```

### Loop Popup (Precision Controls)

**HTML Structure:**
```html
<div id="loop-popup-{id}" class="absolute ... bg-gray-800/95 border-emerald-500/50">
    <!-- Start time control -->
    <div class="flex items-center gap-1">
        <span class="text-[10px] text-gray-500">START</span>
        <input class="time-input-start w-[72px] ... font-mono text-emerald-400" value="0:00.000">
        <div class="flex flex-col">
            <button class="time-up-start">▲</button>
            <button class="time-down-start">▼</button>
        </div>
    </div>
    <!-- End time control -->
    <div class="flex items-center gap-1">
        <span class="text-[10px] text-gray-500">END</span>
        <input class="time-input-end ...">
        <div class="flex flex-col">
            <button class="time-up-end">▲</button>
            <button class="time-down-end">▼</button>
        </div>
    </div>
    <!-- Divider -->
    <div class="w-px h-6 bg-gray-700"></div>
    <!-- Loop controls -->
    <button class="loop-play-btn">🔁</button>
    <button class="loop-stop-btn hidden">⏹</button>
    <span class="loop-duration">0.00s</span>
</div>
```

**Driven by:**
- `createLoopPopup()` - Creates the popup
- `updatePopupPosition()` - Positions above region
- `adjustTime()` - Handles chevron clicks (±10ms)
- `updateRegionFromInputs()` - Handles input changes
- `startLoopPreview()` / `stopLoopPreview()` - Loop playback

### Crate Row

**HTML Structure:**
```html
<div class="crate-row">
    <div class="crate-row-header glass rounded-xl p-4 cursor-pointer"
         onclick="toggleCrateRow({trackId}, this)">
        <div class="flex items-center justify-between">
            <div class="flex items-center space-x-4">
                <div class="w-10 h-10 rounded-lg bg-indigo-500/20">📁</div>
                <div>
                    <h3 class="font-semibold truncate max-w-[200px]">{name}</h3>
                    <p class="text-sm text-gray-400">{stem_count} stems</p>
                </div>
            </div>
            <div class="flex items-center space-x-6">
                <span>{bpm} BPM</span>
                <span>{duration}</span>
                <button onclick="deleteTrack(...)">🗑</button>
                <svg class="crate-chevron">▼</svg>
            </div>
        </div>
    </div>
    <div id="crate-stems-{trackId}" class="hidden mt-3 ml-4 space-y-3">
        <!-- Stem cards loaded on expand -->
    </div>
</div>
```

**Driven by:**
- `renderCrate()` - Creates row HTML
- `toggleCrateRow()` - Expand/collapse logic
- `loadTrackStems()` - Fetches and renders stems

---

## API Endpoints

### Track Processing

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| GET | `/` | `index()` | Serve HTML template |
| POST | `/analyze` | `analyze_audio()` | Analyze file, return BPM |
| POST | `/fetch-url` | `fetch_url()` | Download from URL, return metadata |
| POST | `/upload` | `upload_audio()` | Start stem separation job |
| GET | `/status/{job_id}` | `get_status()` | Poll job progress |
| DELETE | `/job/{job_id}` | `delete_job()` | Clean up job files |

### Crate Management

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| GET | `/crate` | `get_crate()` | List all tracks |
| GET | `/crate/{track_id}` | `get_crate_track()` | Get track with stems |
| DELETE | `/crate/{track_id}` | `delete_crate_track()` | Delete track and files |

### Samples

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| POST | `/sample` | `create_sample()` | Extract region to WAV |
| GET | `/samples` | `get_samples()` | List all samples |
| DELETE | `/samples/{sample_id}` | `delete_sample_endpoint()` | Delete sample |

### Loops

| Method | Endpoint | Handler | Purpose |
|--------|----------|---------|---------|
| POST | `/loop` | `create_loop_endpoint()` | Create looped audio |
| GET | `/loops` | `get_loops()` | List all loops |
| DELETE | `/loops/{loop_id}` | `delete_loop_endpoint()` | Delete loop |

### Static Files

| Mount | Directory | Purpose |
|-------|-----------|---------|
| `/static` | `app/static/` | Static assets |
| `/output` | `app/output/` | Stems and originals |
| `/samples-files` | `app/samples/` | Sample audio files |
| `/loops-files` | `app/loops/` | Loop audio files |

> **Note:** Static mounts use `-files` suffix to avoid conflicts with DELETE endpoints.

---

## Database Functions

### File: `app/database.py`

#### Connection Management

| Function | Line | Purpose |
|----------|------|---------|
| `get_connection()` | 13 | Get SQLite connection with row factory |
| `get_db()` | 21 | Context manager for transactions |
| `init_db()` | 35 | Create tables, run migrations |

#### Track Operations

| Function | Line | Purpose |
|----------|------|---------|
| `create_track(name, bpm, duration, stem_count, original_filename)` | 96 | Insert track, return ID |
| `create_stem(track_id, name, filename, duration)` | 110 | Insert stem, return ID |
| `get_all_tracks()` | 124 | List tracks ordered by created_at DESC |
| `get_track_with_stems(track_id)` | 136 | Get track + stems array |
| `track_exists(name)` | 161 | Check if track name exists |
| `delete_track(track_id)` | 171 | Delete track (cascades to stems) |
| `get_track_by_name(name)` | 185 | Find track by name |
| `update_track_original(track_id, original_filename)` | 196 | Update original_filename |

#### Sample Operations

| Function | Line | Purpose |
|----------|------|---------|
| `create_sample(track_name, stem_name, filename, start_time, end_time, duration)` | 208 | Insert sample |
| `get_all_samples()` | 231 | List samples ordered by created_at DESC |
| `get_sample_by_id(sample_id)` | 243 | Get sample by ID |
| `delete_sample(sample_id)` | 255 | Delete sample |
| `sample_exists(filename)` | 269 | Check if filename exists |

#### Loop Operations

| Function | Line | Purpose |
|----------|------|---------|
| `create_loop(source_type, track_name, stem_name, filename, start_time, end_time, loop_count, duration)` | 281 | Insert loop |
| `get_all_loops()` | 306 | List loops ordered by created_at DESC |
| `get_loop_by_id(loop_id)` | 318 | Get loop by ID |
| `delete_loop(loop_id)` | 330 | Delete loop |
| `loop_exists(filename)` | 344 | Check if filename exists |

---

## Event Flow Diagrams

### File Upload Flow

```
User drops file
    │
    ▼
#file-input change event
    │
    ▼
showFilePreview(file)
    ├── initWaveSurfer()
    ├── wavesurfer.loadBlob(file)
    └── POST /analyze → BPM display
    │
    ▼
User clicks "Split Audio"
    │
    ▼
#upload-form submit event
    │
    ▼
POST /upload
    ├── Show #status-section
    └── startPolling()
        │
        ▼
    GET /status/{job_id} (every 2s)
        │
        ▼ (when complete)
    showResults(data)
        ├── Render stem cards
        ├── loadCrate()
        └── loadSamples() + loadLoops()
```

### Region Selection Flow

```
User Shift+mousedown on waveform
    │
    ▼
setupRegionSelection mousedown handler
    ├── isDragging = true
    ├── Create preview overlay
    └── Remove existing region/popup
    │
    ▼
User drags mouse
    │
    ▼
document mousemove handler
    └── Update preview overlay position/width
    │
    ▼
User releases mouse
    │
    ▼
document mouseup handler
    ├── isDragging = false
    ├── Remove preview overlay
    ├── regions.addRegion()
    ├── createLoopPopup()
    ├── updatePopupPosition()
    └── onRegionCreated(region)
        └── Show Sample button + Loop controls
```

### Loop Preview Flow

```
User clicks loop icon in popup
    │
    ▼
startLoopPreview()
    ├── loopPreviewState.isLooping = true
    ├── Update UI (show stop, hide play)
    ├── wavesurfer.setTime(region.start)
    ├── wavesurfer.play()
    └── requestAnimationFrame(checkPosition)
        │
        ▼
    checkPosition() (called every frame)
        ├── if currentTime >= region.end
        │   └── Restart from region.start
        └── Continue if isLooping
    │
    ▼
User adjusts region (drag or inputs)
    │
    ▼
region-updated or adjustTime()
    └── Loop automatically uses new boundaries
    │
    ▼
User clicks stop or presses Esc
    │
    ▼
stopLoopPreview()
    ├── wavesurfer.pause()
    ├── isLooping = false
    └── Update UI (show play, hide stop)
```

---

## Quick Reference: Element IDs

### Upload Section
- `#upload-form`, `#file-input`, `#file-label`, `#upload-zone`
- `#url-input`, `#fetch-url-btn`, `#fetch-btn-text`
- `#tab-file`, `#tab-url`, `#file-section`, `#url-section`
- `#preview-section`, `#track-info`, `#track-thumbnail`, `#track-title`, `#track-artist`
- `#waveform`, `#waveform-loading`, `#play-btn`, `#play-icon`, `#pause-icon`
- `#current-time`, `#duration`, `#bpm-display`
- `#submit-btn`, `#btn-text`

### Status & Results
- `#status-section`, `#status-title`, `#status-message`
- `#results-section`, `#stems-grid`
- `#error-section`, `#error-message`

### Crate
- `#crate-section`, `#crate-count`, `#crate-list`
- `#crate-stems-{trackId}` (dynamic)

### Samples & Loops
- `#samples-section`, `#samples-count`, `#samples-list`
- `#loops-section`, `#loops-count`, `#loops-list`

### Dynamic Elements (per stem/sample/loop)
- `#waveform-{uniqueId}`
- `#play-btn-{uniqueId}`, `#play-icon-{uniqueId}`, `#pause-icon-{uniqueId}`
- `#time-{uniqueId}`, `#duration-{uniqueId}`
- `#sample-btn-{uniqueId}`, `#sample-btn-text-{uniqueId}`
- `#loop-controls-{uniqueId}`, `#stem-loop-count-{uniqueId}`, `#stem-loop-btn-{uniqueId}`
- `#loop-popup-{uniqueId}` (contains `.time-input-start`, `.time-input-end`, etc.)
