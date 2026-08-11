# Tone reference scan planner

Use `scripts/plan_tone_reference_scan.py` to identify which local Rocksmith `.psarc` files are new or changed relative to a previously generated private tone-reference library.

Example:

```powershell
python scripts/plan_tone_reference_scan.py "C:\Program Files (x86)\Steam\steamapps\common\Rocksmith2014\dlc" --library private\tone_reference_library.json
```

The planner is read-only. It does not unpack packages or modify Rocksmith files. The next bridge stage consumes the listed paths, extracts normalized tone metadata locally, and merges those records into the private library.