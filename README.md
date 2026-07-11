# Video Note Generator

Videós workshopok feldolgozása Obsidian-kompatibilis tanulási jegyzetekké.

## Pipeline

```
SRT → Parser → Cleaner → Chapters → Summarize (AI) → Shots (ffmpeg) → Build (Markdown)
```

| Lépés | Parancs | API |
|-------|---------|-----|
| Parser | `video-notes parse` | nem |
| Cleaner | `video-notes clean` | nem |
| Chapters | `video-notes chapters` | opcionális (`--method ai`) |
| Summarize | `video-notes summarize` | igen |
| Shots | `video-notes shots` | nem (ffmpeg) |
| Build | `video-notes build` | nem |

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
# GOOGLE_API_KEY=...   # Gemini-hez
# OPENAI_API_KEY=...   # OpenAI-hoz
```

Alapértelmezett provider a `config.yaml`-ban: **Mistral**.

```yaml
ai:
  provider: mistral
  model: mistral-small-latest
```

Provider választás CLI-ből (`mistral`, `gemini`, `openai`):

```bash
video-notes summarize output/chapters.json --provider mistral
video-notes summarize output/chapters.json --provider gemini
video-notes summarize output/chapters.json --provider openai
```

### Teljes pipeline egy lépésben

```bash
# Alapértelmezett: input/ → output/001/, majd archiválás processed/001/-be
video-notes process

# Konkrét felirat megadása
video-notes process input/webinar.srt

# Saját kimeneti mappa (--output felülírja az automatikus számozást)
video-notes process input/ --output output/egyedi-mappa/

# API nélkül (csak parse + clean + chapters)
video-notes process input/ --skip-summarize
```

### Automatikus számozás és archiválás

A `process` parancs alapértelmezés szerint:

1. **Számozott kimenet** — `output/001/`, `output/002/`, … (jegyzet, JSON, képek)
2. **Forrás archiválás** — sikeres feldolgozás után a videó + SRT átkerül `processed/001/`-be

Az `input/` mappa így mindig üresen várja a következő videót; a korábbi anyagok nem keverednek.

```yaml
output:
  directory: "output"
  processed_directory: "processed"
  auto_number: true      # output/001/, output/002/, ...
  archive_inputs: true   # processed/001/-be mozgatás siker után
  number_padding: 3      # 001, 002, ...
```

A számláló az `output/` és `processed/` mappák meglévő számozott almappáiból számol tovább.
Ha `--output` opciót adsz meg, a számozás kikapcsol — az archiválás ilyenkor `processed/<fájlnév>/` alá kerül.

### Lépésenként

```bash
# 1. Parser
video-notes parse input/webinar.srt --output output/parsed.json --stats

# 2. Cleaner
video-notes clean input/webinar.srt --output output/cleaned.json --stats

# 3. Chapters (heurisztikus, API nélkül)
video-notes chapters output/cleaned.json --output output/chapters.json --stats

# 4. AI fejezetek (opcionális, API-val)
video-notes chapters output/cleaned.json --method ai --provider mistral --stats

# 5. AI összefoglaló
video-notes summarize output/chapters.json --provider mistral --stats

# 6. Screenshotok (ffmpeg)
video-notes shots output/summary.json

# 7. Obsidian jegyzet
video-notes build output/summary.json --output output/notes.md
```

## Workshop típus testreszabása

Az alapértelmezett konfiguráció Figma / webdesign workshopokra van hangolva.
Más témájú videókhoz a `config.yaml`-ban két helyen érdemes módosítani:

### AI promptok (`project:`)

A fejezetfelismerés és az összefoglaló promptok ezeket a mezőket használják:

| Mező | Hatás |
|------|-------|
| `domain_hints` | Preferált szakkifejezések az AI-nak (címek, kulcsszavak) |
| `practice_context` | A `practice_task` gyakorlati feladat kontextusa |
| `chapters_per_minutes` | Célzott fejezetarány AI módban (pl. `"3-4"` = kb. 1 fejezet / 3–4 perc) |

```yaml
project:
  domain_hints: "Figma, webdesign, UI komponensek (Components, Variants, Auto Layout)"
  practice_context: "Figma / webdesign workshop"
  chapters_per_minutes: "3-4"
```

### Heurisztikus fejezetcímek (`chapters.topic_keywords`)

Ha `chapters.method: heuristic` (alapértelmezett), a fejezetcímeket kulcsszó-alapú
egyeztetés határozza meg — API hívás nélkül.

| Mező | Hatás |
|------|-------|
| `keyword` | Keresett szöveg a transzkriptben |
| `title` | Generált fejezetcím, ha a kulcsszó megtalálható |
| `generic` | Túl általános kulcsszó: csak rövid mondatnál lesz cím (pl. „bevezet”, „figma”) |

```yaml
chapters:
  method: heuristic
  topic_keywords:
    - keyword: "auto layout"
      title: "Auto Layout"
    - keyword: "figma"
      title: "Figma"
      generic: true
```

### Példa: Python workshop

```yaml
project:
  domain_hints: "Python, pytest, virtualenv, type hints, pip"
  practice_context: "Python backend workshop"
  chapters_per_minutes: "4-5"

chapters:
  method: heuristic
  topic_keywords:
    - keyword: "pytest"
      title: "Pytest tesztek"
    - keyword: "virtualenv"
      title: "Virtualenv"
    - keyword: "type hint"
      title: "Type hints"
    - keyword: "bevezet"
      title: "Bevezetés"
      generic: true
```

AI módhoz (`chapters.method: ai` vagy `--method ai`) elég a `project:` szekció
átírása — a `topic_keywords` csak a heurisztikus detektálást érinti.
