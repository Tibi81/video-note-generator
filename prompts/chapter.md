Analyze the workshop transcript below. Each line starts with a timestamp in [HH:MM:SS] format.

Your task:
1. Identify logical topic chapters based on content shifts (not fixed time intervals).
2. For this chunk, return chapters that START within this text.
3. Keep all important topics; do not over-merge unrelated sections.
4. Use clear, concise Hungarian titles (2-6 words) suitable for study notes.
5. Prefer concrete UI/design terms when visible in the text (e.g. Components, Variants, Auto Layout).

Return ONLY valid JSON array, no markdown fences:
[
  {"title": "Bevezetés", "start": "00:04:07"},
  {"title": "Design System alapok", "start": "00:21:14"}
]

Rules:
- `start` must match an existing timestamp from the transcript.
- Titles must be in Hungarian.
- Aim for proportional coverage of this chunk (not too few, not too many).
- Skip pure technical/chat interruptions unless they start a new topic.

Transcript chunk:
{transcript}
