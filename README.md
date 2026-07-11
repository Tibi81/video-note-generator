# Video Note Generator

Videós workshopok feldolgozása Obsidian-kompatibilis tanulási jegyzetekké.

## Fázis 1 — Parser (MVP)

SRT felirat beolvasása, strukturált JSON export, statisztika.

## Fázis 2 — Cleaner

Zaj eltávolítása (kitöltőszavak, chat, technikai részek), duplikátumok szűrése,
tördelt mondatok összevonása időbélyegek megőrzésével.

### Telepítés

```bash
cd video-note-generator
pip install -e ".[dev]"
```

### Használat

```bash
# 1. Parser
video-notes parse input/webinar.srt --output output/parsed.json --stats

# 2. Cleaner (SRT-ből vagy parsed.json-ból)
video-notes clean input/webinar.srt --output output/cleaned.json --stats
video-notes clean output/parsed.json --output output/cleaned.json --stats
```

### Kimenet

- `output/parsed.json` — nyers feliratblokkok
- `output/cleaned.json` — tisztított, összevont blokkok `source_indices`-szel

### Tesztek

```bash
pytest
```

## Pipeline (tervezett)

```
SRT → Parser → Cleaner → Chapters → AI → Screenshots → Markdown → Obsidian
```
