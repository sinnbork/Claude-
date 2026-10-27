---
name: plan-field-map
description: Turn a construction or utility drawing (PDF site plan, street-lighting plan, "vinnuteikning", cable/pipe layout, pole or manhole plan) into a mobile web map for field crews, with the drawing overlaid on Google Maps/satellite, every point (light pole, cabinet, manhole, sign…) as a tappable marker with GPS, directions, checklists, notes, material and progress counts, and a heading-up driving mode, published on GitHub Pages. Use this whenever someone uploads a plan or drawing and wants to find things on site, navigate a new neighbourhood, overlay a drawing on a map, track installation progress per pole/point, or asks for "the same kind of map as the light poles", even if they don't say "skill", "georeference" or "web app".
---

# Plan → field map

Builds a static web app (one `index.html` + `data/`) that lays a PDF plan over a live map, so a crew can walk or drive to each point and tick off work. The first build was 319 street-light poles in Vatnsendahvarf, Kópavogur, used by an Icelandic crew. That version is the template in `assets/app/`.

The work splits into four parts: **read the drawing → georeference it → build the app → publish it**. Most of the judgment is in the first two. The rest is configuration.

## 0. Setup

```bash
pip install -q pymupdf pillow numpy        # PDF vectors/text + image work
S=<this skill dir>/scripts
```
For Iceland, also get the address register: `pip download --no-deps iceaddr -d /tmp/dl && unzip -q -o /tmp/dl/iceaddr-*.whl -d /tmp/ice`. The database is then at `/tmp/ice/iceaddr/iceaddr.db`. It's the Staðfangaskrá, with WGS84 coordinates for every address, including streets that are still being built. PyPI is usually reachable even when map servers are blocked in a sandbox.

## 1. Read the drawing

```bash
python3 $S/pdf_inventory.py plan.pdf inv/      # overview.png, words.json, shapes.txt
python3 $S/crop.py plan.pdf X Y 30 800 zoom.png # zoom in on a sample position
```
Look at `overview.png` first, then zoom into a few points. CAD exports draw each symbol as a repeated vector signature. `shapes.txt` lists the most common ones with a sample position. The light-pole symbol was a blue ring: stroke `0,0.5,1`, 1.92 × 1.92 pt, 10 path items. Each ring was drawn twice, and the script merges the duplicates.

Then extract the points:
```bash
python3 $S/extract_symbols.py plan.pdf inv/words.json --stroke 0,0.5,1 --size 1.92 --items 10 \
  --id-regex '\d\d\.\d[-.]\d\d' --code-regex '[A-L]' --code-color ff0000 --out symbols.json
```
Check the printout. **Symbols and ID labels should match one-to-one.** If they don't, loosen the ID regex: some labels come out as `03.1.02` or with spaces inside them, which the script strips. Any duplicate ID is probably a real drafting error. Keep both and tell the user. Code letters next to the symbols (here A–I) turned out to mean the **hat/lamp type**. Ask the user what the codes mean rather than guessing, and don't name them until you know.

Secondary annotations, like the existing poles marked "Ný staðsetning" (new location) in that plan, are worth a separate layer. Position them relative to their text label (`words.json`), and look at a crop to confirm which dot is the new position and which is the crossed-out old one. Write them as `[{id, px, py}]` for `--extra`.

## 2. Georeference

Plans usually carry **no coordinates and are often rotated**. The first plan was 44.5° off north. So fit an affine transform from matched points rather than assuming north-up.

**Iceland (automatic):** give three house-number labels you can read on crops, spread across the sheet. The script then matches every number label on the sheet to the register and refines the fit:
```bash
python3 $S/georef.py --iceaddr /tmp/ice/iceaddr/iceaddr.db --words inv/words.json \
  --anchor "811,197,Sólarhvarf,30" --anchor "840,378,Skyggnishvarf,25" --anchor "1795,473,Turnahvarf,4" --out georef.json
```
A good sheet gives several hundred matches with a ~2–3 m median. If you see few matches or a median over 5 m, an anchor is wrong. Re-check its street on a crop.

**Elsewhere:** collect at least 3 control points spread wide (more is better): road junctions, building corners or survey marks, with their lat/lon from the user, Google Maps or survey data. Put them in a CSV (`pdf_x,pdf_y,lat,lon`) and run `georef.py --control points.csv --out georef.json`. If the region has an open address dataset reachable from the sandbox, the Iceland approach adapts easily.

Then build and check:
```bash
python3 $S/build_plan.py plan.pdf georef.json symbols.json docs/ --extra extra.json --source "drawing name"
python3 $S/check_alignment.py docs/data /tmp/ice/iceaddr/iceaddr.db check.png 1000 300 2600 1500   # Iceland
```
Look at `check.png`. The register's addresses should sit inside the right buildings, and the green rings should sit on the drawn symbols. Tell the user the real accuracy (e.g. "median 2.3 m"). Also tell them to set out from survey data before digging.

## 3. Build the app

Copy `assets/app/index.html` into the output folder (e.g. `docs/`) next to `data/`. Edit only the **`PROJECT` block at the top of the script**:
- `title`, `source` (the attribution/accuracy note in the menu)
- `storePrefix`: **make it unique per project**. Every app on `user.github.io` shares one browser storage, so two projects with the same prefix would overwrite each other's ticks.
- `checks`: the work steps on each card, with the letter shown on the map (light poles: Staur/Box/Hattur → S/B/H)
- `faces`: a pick-one finish/colour option, shown as a dot (light poles: brown/black/grey). Use `[]` to hide it.
- `codeUpCheck`: which check means the coded item (the hat) is up, used for the per-code Up/Left/Total table
- `materialCheck` + `materials`: one material set is used per point with that check ticked. Use `[]` to hide the table.

What the template already does, so you don't rebuild it:
- Google Maps when a key is given (`?key=`, ☰ menu, or the `GOOGLE_MAPS_API_KEY` const), otherwise OpenStreetMap/Esri satellite through Leaflet.
- A rotated, semi-transparent overlay of the drawing.
- Search by ID, deep links (`#ID`), GPS, the nearest point, and Google Maps directions.
- Checkboxes, the colour option and notes. Marking a point installed ticks every check. A ready point gets a green ring. A red `*` marks a point with notes.
- Per-code counts, material counts, and CSV/GeoJSON export.
- Driving mode (⬆): the map rotates by GPS course while moving and falls back to the compass when slow or stopped. Gestures are locked while rotated, and +/− buttons zoom instead.

**The UI is in Icelandic**, because the original crew included an older Icelandic user who asked for it. Match the language to the crew. If they need another language, translate every visible string (the HTML, toasts, `confirm`, the table headers, CSV headers and the Leaflet layer names) and set `<html lang>` and Google's `language=`/`region=` URL parameters.

The ticks are saved **per device** (localStorage). Say so when you hand over. Exports exist so a lead can collect them. Shared live state would need a backend, so offer it rather than build it unasked.

Test before publishing:
```bash
mkdir -p /tmp/smoke && (cd /tmp/smoke && npm pack leaflet@1.9.4 -s && tar xzf leaflet-1.9.4.tgz)
node $S/smoke_test.js docs /tmp/smoke     # screenshots + JSON summary; expect no pageErrors
```
Look at the screenshots, especially the pole card and the menu at phone width (390 px). The Google path can't be tested without a key and network access, so say that it wasn't tested.

## 4. Publish (GitHub Pages)

- Commit `docs/` on a branch, push, and merge into `main` when the user asks.
- From a cloud session, the Pages settings API is blocked, so the **user has to enable Pages themselves**. Give click-by-click steps: open `github.com/<owner>/<repo>/settings/pages`, set Source to *Deploy from a branch*, pick the branch and the **`/docs`** folder, and click **Save**. People often miss Save. A private repo needs GitHub Pro/Team, or the repo has to be made public: the **Danger Zone** at the bottom of Settings → General, which isn't in the mobile app. A Pages site is public either way, so tell the user the drawing will be visible to anyone with the link.
- Verify the deploy with `gh api repos/<o>/<r>/actions/runs?per_page=1` (the *pages build and deployment* run) and `gh api repos/<o>/<r> --jq .has_pages`. github.io itself is often unreachable from the sandbox. Deploys can sit queued for a few minutes, so wait in the background and report when the run succeeds.
- HTTPS (which Pages provides) is required for GPS on phones.

## Working with the user

This is typically a field supervisor, not a developer. Keep replies short and concrete ("tap ⬆", "refresh the page"), send a phone-size screenshot of new features, and after each change say what was tested and what wasn't. Expect a stream of small requests once crews use the map, like the ones that shaped the template: extra checkboxes, a colour option, material tracking, a notes marker, Icelandic text, driving mode. Make each request a small, tested change, and publish it the same way each time.
