# Video Note Generator

Videós workshopok feldolgozása Obsidian-kompatibilis tanulási jegyzetekké.

## Fázis 1 — Parser (MVP)

SRT felirat beolvasása, strukturált JSON export, statisztika.

## Fázis 2 — Cleaner

Zaj eltávolítása (kitöltőszavak, chat, technikai részek), duplikátumok szűrése,
tördelt mondatok összevonása időbélyegek megőrzésével.

## Fázis 3 — Chapter Detector

Tisztított szöveg logikus fejezetekre bontása időbélyegekkel és címekkel.
Alapértelmezés: heurisztikus módszer; opcionálisan AI (`--method ai`).

### Telepítés

```bash
cd video-note-generator
pip install -e ".[dev]"

# AI módhoz (opcionális)
pip install -e ".[ai]"
```

### AI provider beállítás

Másold át a `.env.example` fájlt `.env` néven, és add meg a kulcsot:

```env
MISTRAL_API_KEY=your-key-here
```

Alapértelmezett provider a `config.yaml`-ban: **Mistral** (ingyenes tier).

```yaml
ai:
  provider: mistral
  model: mistral-small-latest
```

Provider választás CLI-ből (`mistral`, `gemini`, `openai`):

```bash
# Mistral (alapértelmezett)
video-notes chapters output/cleaned.json --method ai --provider mistral
video-notes summarize output/chapters.json --provider mistral

# Gemini (ingyenes kvóta)
video-notes summarize output/chapters.json --provider gemini

# OpenAI
video-notes summarize output/chapters.json --provider openai
```

### Használat

```bash
# 1. Parser
video-notes parse input/webinar.srt --output output/parsed.json --stats

# 2. Cleaner
video-notes clean input/webinar.srt --output output/cleaned.json --stats

# 3. Chapters (heurisztikus, API nélkül)
video-notes chapters output/cleaned.json --output output/chapters.json --stats

# 4. AI összefoglaló (MISTRAL_API_KEY vagy GOOGLE_API_KEY a .env-ben)
video-notes summarize output/chapters.json --provider mistral --stats
```

### Kimenet

- `output/parsed.json` — nyers feliratblokkok
- `output/cleaned.json` — tisztított, összevont blokkok
- `output/chapters.json` — fejezetek címekkel és időbélyegekkel

### Tesztek

```bash
pytest
```

## Fázis 5 — Screenshots + Markdown

ffmpeg screenshot kivágás és Obsidian-kompatibilis `notes.md` generálás.

### Használat

```bash
# 5. Screenshotok (ffmpeg)
video-notes shots output/summary.json

# 6. Obsidian jegyzet
video-notes build output/summary.json --output output/notes.md
```

### Kimenet

- `output/images/001.png` … — screenshotok
- `output/screenshots.json` — manifest
- `output/notes.md` — Obsidian jegyzet

## Pipeline

```
SRT → Parser → Cleaner → Chapters → Summarize → Shots → Build → Obsidian
```
