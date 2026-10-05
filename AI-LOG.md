# AI assistance log

This log records AI assistance used during development of the Noongar
Language Learner. It describes implementation support, not authorship or
verification of Noongar language content.

| Work area | AI assistance | Human review / verification |
|---|---|---|
| Learner features | Helped implement category browsing, category-scoped quizzes, flashcards, dictionary search, and progress/saved-word features in the desktop and web apps. | The project owner reviewed the application and requested changes to interaction and presentation. |
| Pronunciation | Helped add playback via device-provided text-to-speech. Considered generated audio, but that approach was removed after the project owner chose not to use a paid generation service. | The interface indicates that device speech is approximate; no generated WAV pronunciations are included. |
| Dictionary insights | Helped add descriptive category counts and percentages to both application versions. | The chart describes the supplied rows only and does not claim frequency, cultural significance, or language authority. |
| Study progress | Helped add local per-date correct/attempted counts and an accuracy trend chart to the desktop and web versions. | Daily rates combine quiz questions answered on each local calendar date; days without quiz answers are omitted. |
| Data helpers and tests | Helped extract shared Python data helpers and author unit tests for loading, searching, category summaries, quiz choices, and daily accuracy aggregation. | The 23-test `unittest` suite passed using the Pylance-selected Python interpreter. |
| Documentation | Helped draft setup/use instructions, the architecture diagram, and this assistance log. | Project-specific dataset provenance, permissions, and attribution remain to be verified by the project owner. |

AI was not used as a source or authority for the dictionary's Noongar
translations, spellings, cultural information, or usage guidance. Those data
must be checked with appropriate sources and rights holders. No dataset
source or reuse licence is asserted in this log because it has not been
independently established.
