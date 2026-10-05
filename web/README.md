# Noongar Language Learner web app

This is a responsive, installable web app for iPhone and Android. It includes
dictionary search, category browsing with English/Noongar sorting, flashcards,
quizzes, saved words and custom lists, missed-word practice, study progress,
and adjustable text size. Personal data is stored in this browser on this
device; it is not synced between devices. It does not use the downloaded dictionary images. Speaker buttons
use the device's built-in text-to-speech voice, which may not pronounce Noongar
words accurately. The app does not download or use generated WAV files. Quiz
totals, reviewed words, missed words, saved words and lists, and text-size
preference persist between visits. The Study Progress page can clear quiz
totals, reviewed words, and missed-word practice while leaving saved lists
intact.

## Published app

The app is live over HTTPS at <https://celadon-puppy-c1389f.netlify.app/>.
Anyone with the link can open it in a browser. Each visitor's study data stays
in that browser's local storage.

## Prepare the latest dictionary data

The web app reads `Noongar categories.csv` from this folder. After editing the
project's main CSV, run `./sync_web_data.command` from the project folder to
copy the latest dictionary into this web app.

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
