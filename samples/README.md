# Sample photos (local only)

Regression images used during development. They are ignored by Git and Docker
because they are photos of real people. Run the regression check with:

```powershell
.venv\Scripts\python scripts\evaluate_samples.py            # pipeline only, no API calls
.venv\Scripts\python scripts\evaluate_samples.py --vlm Gemini
```

Annotated outputs and a summary JSON are written to `outputs/samples/`.
