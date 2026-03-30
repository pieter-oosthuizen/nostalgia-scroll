# NostalgiaScroll

Generate an offline, scrollable website from a WhatsApp **iOS export** (ZIP or extracted folder).

## Privacy & responsibility

- **You are responsible for your data and privacy.** This tool runs locally, but chat exports and generated sites can contain extremely sensitive personal information and media.
- **No warranties.** The author(s) of this tool take **no responsibility or liability** for privacy leaks, accidental publication, or any resulting harm.
- **Do not commit exports or output.** Make sure you never commit `Source/` or `output/` to git (this repo includes a `.gitignore` for that).

## Quick start

1) Put your export zip into `Source/` (example: `Source/WhatsApp Chat with Alice.zip`).

2) (Optional) Create a virtual environment and install requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

3) Run (pick one):

```bash
# Run the package module
python -m nostalgia_scroll
```

4) Open:
- `output/site/index.html`

## Options

```bash
python -m nostalgia_scroll --help
```

## Using a different Source folder / ZIP

```bash
# Use a different Source folder
python -m nostalgia_scroll --source-dir "/path/to/Source"

# If your Source folder is an already-extracted WhatsApp export (contains `_chat.txt`)
python -m nostalgia_scroll --source-dir "../WhatsApp Chat - Someone/"

# Or point directly at a ZIP
python -m nostalgia_scroll --zip "/path/to/WhatsApp Export.zip"
```

## Notes
- This tool reads the chat `.txt` inside the ZIP and ignores media files for now (it uses message timestamps and text).
- If you have multiple ZIPs in `Source/`, it picks the most recently modified one. You can override with `--zip /path/to/export.zip`.
- Output is always written to `output/site/`.
- The generated site uses **infinite scroll** and month jump links; it loads month chunks via local script files in `output/site/months/`.
