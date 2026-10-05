# Noongar Language Learner web app

This is a responsive, installable web app for iPhone and Android. It includes
dictionary search, category browsing with English/Noongar sorting, flashcards,
quizzes, device text-to-speech buttons, and quiz statistics for the current
page visit. It does not use the downloaded dictionary images. Generated WAV
pronunciations are played when available; otherwise speech falls back to the
device voice. Machine-generated pronunciation may be inaccurate for Noongar.
Quiz statistics reset when the page is reloaded or reopened.

## Published app

The app is live over HTTPS at <https://celadon-puppy-c1389f.netlify.app/>.
Anyone with the link can open it in a browser. Each visitor's quiz statistics
stay in that page session only.

## Prepare the latest dictionary data

The web app reads `Noongar categories.csv` from this folder. After editing the
project's main CSV, run `./sync_web_data.command` from the project folder to
copy the latest dictionary into this web app.

## Generate pronunciation audio

The project includes `generate_pronunciations.py`, which creates one Google
Gemini TTS WAV for each distinct Noongar word and saves it under `web/audio`.
It resumes from its manifest and existing files. The dictionary currently
contains 628 distinct Noongar words. Review Google's API terms and current
pricing before generation; the free tier may use submitted content to improve
Google products, and paid-tier usage may incur charges.

Create an API key in Google AI Studio, then set it locally without adding it to
the source files:

```sh
read -s "GEMINI_API_KEY?Google AI Studio API key: "
echo
export GEMINI_API_KEY
python3 generate_pronunciations.py --limit 1
```

After listening to the sample WAV, generate the remaining words by running:

```sh
python3 generate_pronunciations.py
unset GEMINI_API_KEY
```

The default voice and broad-Australian style can be customized with
`--voice` and `--style`. The generated clips are used in both apps. Redeploy
the contents of `web/` to publish the web audio; rebuild the macOS app with
`./build_app.command` to include audio in its bundle.

## Preview on this computer

From the project folder, run:

```sh
cd web
python3 -m http.server 8000
```

Open <http://localhost:8000> in a browser. A local server is required because
the browser does not allow the app to fetch a CSV from a `file://` page.

## Use on a phone

Publish the contents of this `web` folder, including the CSV, to a static web
host that provides HTTPS. Open that HTTPS link on the phone:

- **iPhone:** Safari → Share → Add to Home Screen.
- **Android:** Chrome → menu → Install app or Add to Home screen.

The app is installable and caches its files for offline use after its first
successful online visit.

## Update the published app

After changing the web app files, sign in to the Netlify account that owns the
site and redeploy the contents of this `web` folder. Do not upload the whole
project folder, which also contains unrelated files.
