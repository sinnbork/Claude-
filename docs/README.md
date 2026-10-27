# Vatnsendahvarf street lighting – field map

Web app that overlays the street-lighting working drawing
(`23395_RAF-götulýsing_vinnuteikning`) on a live map, so crews can find each new light pole on site.

## Features
- Plan drawing overlaid on the map, with an opacity slider.
- All 319 new poles shown as markers, coloured by the letter code on the drawing (A–I). Search by pole ID (e.g. `03.3-01`).
- The 9 existing poles marked "Ný staðsetning" (new location) on Turnahvarf, shown as ◆.
- Live GPS position, the nearest pole, and the distance to the selected pole.
- **Directions** opens Google Maps navigation to the pole.
- "Mark installed" progress tracking (saved in this browser), with CSV/GeoJSON export.
- Deep link to a pole: `index.html#03.3-01`.

## Base map
- **Google Maps**: needs a Maps JavaScript API key. Open the app with `?key=YOUR_KEY` once, enter it under ☰ → *Google Maps API key…*, or set `GOOGLE_MAPS_API_KEY` in `index.html`. Restrict the key to your site's URL in Google Cloud Console.
- With no key, the app falls back to OpenStreetMap and Esri satellite imagery.

## How positions were derived
The drawing has no coordinates. It was georeferenced by matching 352 house numbers on the plan to the
Icelandic address register (Staðfangaskrá, via the `iceaddr` dataset), using a least-squares affine fit.
Median residual is about 2.3 m and RMS about 3 m. Pole positions are the centres of the pole symbols
on the drawing. Treat them as approximate and set out from the survey data before installing.

## Hosting
This is a static site. With GitHub Pages: Settings → Pages → *Deploy from a branch* → choose the branch and the `/docs` folder.
Location (GPS) needs HTTPS, which GitHub Pages provides.
