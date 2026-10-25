# Live demo

The [live demo](https://sudemkirmiz.github.io/skincare-vision-ai/) is the same React app built with `--mode demo` and published by `.github/workflows/pages.yml` on every push to `main` that touches `frontend/`. In that build the API client answers `/api/*` from `frontend/src/demo/` instead of a server, so it needs no backend, model or API key. The regular build contains none of the demo code or its sample files.

What visitors can do: run the analysis of the sample portrait, browse every tab, tick routines (kept in their browser only), open the PDF report, check the sample ingredient list, read the history and create the journey card. Uploading their own photo, editing the shelf and the coach answer with a clear message instead of invented results.

The recorded data is rebased to the visitor's date at runtime, so the sample weeks always end today.

## Rebuilding the demo and the README media

| Step | Command |
| --- | --- |
| Record the demo data from the real backend (offline, no AI call) | `.venv\Scripts\python scripts\build_demo_fixtures.py` |
| Build the demo locally | `cd frontend; $env:VITE_BASE="/skincare-vision-ai/"; npm run build:demo` |
| Preview it | `npx vite preview --mode demo --outDir dist-demo --port 4180` |
| Record the README animation (every page and tab, in order) | `node scripts/demo-tour.mjs video`, then `python ..\scripts\make_demo_animation.py` |
| Retake the README screenshots | `node scripts/demo-tour.mjs shots` |

The animation is captured from Chrome's screencast and encoded as animated WebP, which keeps text and the photo sharp at a fraction of a GIF's size.

The sample portrait is AI-generated (see [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md)). The care comment in the demo is a real Gemini response for that photo, stored so rebuilding the demo spends no API quota.
