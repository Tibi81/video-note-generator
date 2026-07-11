Analyze this workshop chapter and create structured study notes in Hungarian.

Chapter title: $title
Time range: $start -> $end

Chapter transcript:
$transcript

Return ONLY valid JSON, no markdown fences:
{
  "summary": "3-5 mondatos összefoglaló, tartalmi, tanulásra használható",
  "key_points": [
    "⭐ Fő tanulság 1",
    "⭐ Fő tanulság 2",
    "⭐ Fő tanulság 3"
  ],
  "keywords": ["kulcsszó1", "kulcsszó2", "kulcsszó3"],
  "practice_task": "Egy konkrét gyakorlati feladat, amit a néző kipróbálhat",
  "screenshot": {
    "timestamp": "HH:MM:SS",
    "reason": "Miért érdemes itt screenshotot készíteni"
  }
}

Rules:
- Language: Hungarian
- Use ONLY information from the transcript above. Do not invent facts, tools, or steps.
- Keep all important technical information from the transcript
- Remove chat noise, filler words, and off-topic interruptions
- `key_points`: 3-5 bullet items, each starting with ⭐
- `timestamp` must be between $start and $end (use HH:MM:SS format)
- If no screenshot is needed, set `screenshot` to null
- `practice_task` should be actionable and relevant to: $practice_context
- Prefer concrete terms from the domain when applicable: $domain_hints
