# Alternate full-score triangulation

A second private full-score Guitar Pro 5 file is available for Product Reality testing. The file itself must remain outside Git.

Current private test file identity:

- local filename: `Full Form ultimate-tabs-metallica-for-whom-the-bell-tolls-636.gp5`
- SHA-256: `1309fd8081df5b84ddb36f2a158f239b8fd8157ea1dc3ae48c2ddcc243fd0eff`
- size observed during development: 116,766 bytes

The new alternate-score comparison layer does not assume this file is better than the registered GP score. It compares both using the same importer and reports Bass/Lead/Rhythm structural agreement or disagreement. No artist/title-specific behavior is encoded.

The diagnostic chain is now:

1. registered GP source interpretation;
2. alternate GP source interpretation;
3. EOF source compatibility evidence;
4. EOF recording-clock observations;
5. final shared-timeline Rocksmith projection.

If 1–3 agree while 4–5 disagree, the likely defect is downstream score-to-recording timing. If 1 and 2 disagree, exact role/source differences remain visible for human review instead of being silently resolved.
