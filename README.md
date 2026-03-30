# NostalgiaScroll

Generate an offline, scrollable website from a WhatsApp **iOS export** (ZIP or extracted folder).

## Privacy & responsibility

- **You are responsible for your data and privacy.** This tool runs locally, but chat exports and generated sites can contain extremely sensitive personal information and media.
- **No warranties.** The author(s) of this tool take **no responsibility or liability** for privacy leaks, accidental publication, or any resulting harm.
- **Do not commit exports or output.** Make sure you never commit `Source/` or `output/` to git (this repo includes a `.gitignore` for that).

## Prerequisites

- **Python**: 3.10+
- **Node.js + npm**: required to compile Tailwind CSS during generation (`npm install` once, then the generator uses `npx tailwindcss`).

## Quick start

1) Put your export zip into `Source/` (example: `Source/WhatsApp Chat with Alice.zip`).

2) Install build tooling (Tailwind CSS compiler):

```bash
npm install
```

3) (Optional) Create a virtual environment and install requirements:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
```

4) Run:

```bash
python -m nostalgia_scroll
```

5) Open:
- `output/site/index.html`

## Exporting a chat from WhatsApp (iOS)

1) Open **WhatsApp** on your iPhone.

2) Open the chat you want to export (1:1 chats work best).

3) Tap the contact/group name at the top to open **Chat Info**.

4) Scroll down and tap **Export Chat**.

5) Choose **Attach Media** (recommended if you want images to show up).

6) Share/save the export:
- **Save to Files** → pick a folder you can access on your Mac (iCloud Drive works well), or
- AirDrop it to your Mac.

7) On your Mac, place the resulting **ZIP** into the tool’s `Source/` folder (or extract it and point `--source-dir` at the extracted folder containing `_chat.txt`).

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
- This tool reads the chat `.txt` inside the ZIP, copies attached media into the generated site, and renders images inline.
- If you have multiple ZIPs in `Source/`, it picks the most recently modified one. You can override with `--zip /path/to/export.zip`.
- Output is always written to `output/site/`.
- The generated site is a **single long page** (no lazy loading). Year/month links jump to anchors within the page.
