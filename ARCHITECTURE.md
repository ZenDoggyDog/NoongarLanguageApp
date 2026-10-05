# Application architecture

```mermaid
flowchart LR
    CSV["Noongar categories.csv"]
    SYNC["sync_web_data.command"]
    WEBCSV["web/Noongar categories.csv"]
    DATA["noongar_data.py<br/>CSV loading · search · summaries · quiz options"]
    DESKTOP["noongar.py<br/>Tkinter desktop UI"]
    WEBUI["web/app.js<br/>Browser UI, search, categories,<br/>insights, flashcards and quizzes"]
    HTML["web/index.html<br/>Navigation and app shell"]
    CSS["web/styles.css<br/>Responsive presentation"]
    STORAGE["Device-local study data<br/>JSON / localStorage, including daily quiz accuracy"]
    TESTS["tests/test_noongar_data.py<br/>unittest"]
    DEVICE["Built-in device speech"]
    USER["Learner"]

    CSV --> DATA
    CSV --> SYNC --> WEBCSV
    DATA --> DESKTOP
    WEBCSV --> WEBUI
    HTML --> WEBUI
    CSS --> WEBUI
    DESKTOP <--> STORAGE
    WEBUI <--> STORAGE
    DATA --> TESTS
    DESKTOP --> DEVICE
    WEBUI --> DEVICE
    USER <--> DESKTOP
    USER <--> WEBUI
```

The desktop app reads the source CSV through the shared Python data module.
When the CSV changes, `sync_web_data.command` copies it into the static web
folder. The browser app fetches that copy directly and implements its own CSV
reader because it runs without a Python server. The chart in each interface
summarises category entry counts; it does not infer word frequency or cultural
significance. Both applications keep learner progress and per-calendar-day
quiz results on the user's device. Daily accuracy combines all quiz questions
answered on that date; dates with no quiz answers have no chart point.
