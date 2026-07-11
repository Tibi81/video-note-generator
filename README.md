# Video Note Generator

Videós workshopok feldolgozása Obsidian-kompatibilis tanulási jegyzetekké.

## Fázis 1 — Parser (MVP)

SRT felirat beolvasása, strukturált JSON export, statisztika.

### Telepítés

```bash
cd video-note-generator
pip install -e ".[dev]"
```

### Használat

```bash
video-notes input/webinar.srt --output output/parsed.json --stats
```

### Kimenet

- `output/parsed.json` — strukturált feliratblokkok időbélyegekkel
- Konzol statisztika: blokk szám, időtartam, szószám

### Tesztek

```bash
pytest
```

## Pipeline (tervezett)

```
SRT → Parser → Cleaner → Chapters → AI → Screenshots → Markdown → Obsidian
```
