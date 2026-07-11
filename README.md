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

### Használat

```bash
# 1. Parser
video-notes parse input/webinar.srt --output output/parsed.json --stats

# 2. Cleaner
video-notes clean input/webinar.srt --output output/cleaned.json --stats

# 3. Chapters (heurisztikus)
video-notes chapters output/cleaned.json --output output/chapters.json --stats

# 3. Chapters (AI — OPENAI_API_KEY szükséges a .env-ben)
video-notes chapters output/cleaned.json --method ai --stats
```

### Kimenet

- `output/parsed.json` — nyers feliratblokkok
- `output/cleaned.json` — tisztított, összevont blokkok
- `output/chapters.json` — fejezetek címekkel és időbélyegekkel

### Tesztek

```bash
pytest
```

## Pipeline (tervezett)

```
SRT → Parser → Cleaner → Chapters → AI Summary → Screenshots → Markdown → Obsidian
```
