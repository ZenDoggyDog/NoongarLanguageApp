# Noongar Language Learner

A desktop and browser-based learning application for exploring a Noongar
vocabulary dictionary. Learners can search entries, browse categories, use
flashcards, take quizzes, review missed answers, save words and study lists,
and track study progress stored on their device.

## Requirements

- Python 3.10 or later for the desktop app and automated tests.
- A modern browser for the web app. A local HTTP server is required to load
  the CSV; opening the HTML directly as a `file://` URL will not work.
- Tkinter, included with most standard Python installations, for the desktop
  interface.

## Run the desktop app

From this directory:

```sh
python3 noongar.py
```

The app reads `Noongar categories.csv` beside `noongar.py`. It stores study
progress in `~/.noongar-language-learner.json` on the current computer.

To build the macOS application bundle, run:

```sh
./build_app.command
```

The script uses PyInstaller and writes the bundle to `dist/Noongar Language
Learner.app`.

## Run the web app locally

From this directory:

```sh
./sync_web_data.command
cd web
python3 -m http.server 8000
```

Open <http://localhost:8000>. The web version is a static PWA; no application
server or external JavaScript package is required. Deployment notes for the
published site are in [web/README.md](./web/README.md).

## Use the app

- **Search Dictionary** finds English and Noongar text.
- **Browse Categories** lists the available topics and their entries.
- **Dictionary Insights** visualises the number and share of dictionary rows
  in each category. This is descriptive dataset analysis, not a claim about
  word frequency, cultural importance, or language usage.
- **Browse Flashcards** supports recall practice.
- **Interactive Quiz** supports an individual category or the whole
  dictionary. Distractors for a category quiz are drawn only from that
  category.
- **Study Progress** graphs daily quiz accuracy from the learner's local
  device history. Each point combines all questions answered on that local
  calendar date; dates without quiz answers do not appear.
- **Saved Words & Lists**, **Practice Missed Words**, and **Study Progress**
  provide local study tools.
- Speaker controls use the device's built-in text-to-speech and may not
  accurately pronounce Noongar.

The apps store personal study data, including daily quiz accuracy, on the
current device. Web data is kept in that browser's local storage. Data is not
synced between devices. Both versions display the educational disclaimer at
the bottom of the app.

## Dictionary data and attribution

The desktop and web apps use `Noongar categories.csv`, with columns for
English, Noongar, and Category. The loader trims values, ignores incomplete
word rows, supports a missing Category column by marking entries
“Uncategorised”, and checks for the required English and Noongar columns.

**The source, authorship, and reuse licence of the current CSV have not yet
been independently verified.** Do not treat the presence of a scanned
dictionary PDF in the project as proof that it is the CSV's source or that
either resource is licensed for redistribution. Confirm the CSV's provenance,
permission, and required attribution with the project owner or rights holder
before public release or redistribution. Cultural and orthographic variation
is acknowledged in the in-app disclaimer.

## Tests

Run the automated standard-library test suite from this directory:

```sh
python3 -m unittest discover -s tests -v
```

The tests exercise CSV loading and validation, dictionary search, category
summaries, and quiz-option construction.

## Project structure

- `noongar.py` — desktop Tkinter application.
- `noongar_data.py` — shared, testable CSV, search, category-summary, and quiz
  option functions used by the desktop application.
- `Noongar categories.csv` — desktop vocabulary data.
- `web/` — static browser/PWA application and its copy of the vocabulary CSV.
- `tests/` — automated unit tests.
- [ARCHITECTURE.md](./ARCHITECTURE.md) — architecture and data-flow diagram.
- [AI-LOG.md](./AI-LOG.md) — record of AI-assisted development and checks.

