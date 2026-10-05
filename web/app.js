"use strict";

const CSV_URL = "./Noongar%20categories.csv?v=7";
const ALL_CATEGORIES = "All categories";

const appElement = document.querySelector("#app");
const statusElement = document.querySelector("#dictionary-status");
const navButtons = [...document.querySelectorAll(".tab")];
let vocabulary = [];
let categories = [];
let currentView = "home";
let flashcards = [];
let flashcardIndex = 0;
let revealed = false;
let quiz = null;
let deferredInstallPrompt = null;

function parseCsv(text) {
  const rows = [];
  let row = [];
  let field = "";
  let quoted = false;

  for (let index = 0; index < text.length; index += 1) {
    const character = text[index];
    if (quoted) {
      if (character === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (character === '"') {
        quoted = false;
      } else {
        field += character;
      }
    } else if (character === '"') {
      quoted = true;
    } else if (character === ",") {
      row.push(field);
      field = "";
    } else if (character === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += character;
    }
  }
  if (field.length || row.length) {
    row.push(field.replace(/\r$/, ""));
    rows.push(row);
  }
  if (quoted) {
    throw new Error("The dictionary CSV has an unfinished quoted field.");
  }
  return rows;
}

function readDictionary(text) {
  const rows = parseCsv(text.replace(/^\uFEFF/, ""));
  if (!rows.length) throw new Error("The dictionary CSV is empty.");
  const headers = rows[0].map((header) => header.trim().toLocaleLowerCase());
  const englishIndex = headers.indexOf("english");
  const noongarIndex = headers.indexOf("noongar");
  const categoryIndex = headers.indexOf("category");
  if (englishIndex < 0 || noongarIndex < 0) {
    throw new Error("The CSV needs English and Noongar columns.");
  }
  return rows.slice(1)
    .map((values) => ({
      english: (values[englishIndex] || "").trim(),
      noongar: (values[noongarIndex] || "").trim(),
      category: (categoryIndex < 0 ? "" : values[categoryIndex] || "").trim() || "Uncategorised",
    }))
    .filter((item) => item.english && item.noongar);
}

const stats = { attempted: 0, correct: 0 };

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function button(text, onClick, className = "button") {
  const control = element("button", className, text);
  control.type = "button";
  control.addEventListener("click", onClick);
  return control;
}

function createPronounceButton(word) {
  const supported = "speechSynthesis" in window
    && typeof window.SpeechSynthesisUtterance === "function";
  const control = button(
    "🔊",
    () => pronounceNoongarWord(word),
    "button button-secondary speaker-button",
  );
  control.setAttribute("aria-label", `Pronounce Noongar word ${word}`);
  control.title = "Play an approximate pronunciation using your device voice.";
  control.disabled = !supported;
  return control;
}

function pronounceNoongarWord(word) {
  const synthesis = window.speechSynthesis;
  const utterance = new window.SpeechSynthesisUtterance(word);
  const voices = synthesis.getVoices();
  const australianVoices = voices.filter((candidate) =>
    candidate.lang.toLocaleLowerCase().replace("_", "-").startsWith("en-au"),
  );
  const voice = australianVoices.find((candidate) => candidate.localService)
    || australianVoices[0];
  if (voice) {
    utterance.voice = voice;
  }
  utterance.lang = "en-AU";
  utterance.rate = 0.75;
  utterance.pitch = 0.9;
  utterance.onerror = (event) => {
    console.error(`Could not pronounce "${word}" with device speech:`, event.error);
  };
  synthesis.cancel();
  synthesis.speak(utterance);
}

function selectField(labelText, options, selectedValue, onChange, labelFor) {
  const wrapper = element("div", "field");
  const label = element("label", "", labelText);
  const select = element("select", "select");
  select.id = labelFor;
  for (const option of options) {
    const optionElement = element("option", "", option);
    optionElement.value = option;
    select.append(optionElement);
  }
  select.value = selectedValue;
  select.addEventListener("change", onChange);
  label.htmlFor = labelFor;
  wrapper.append(label, select);
  return { wrapper, select };
}

function page(title, description) {
  appElement.replaceChildren();
  const heading = element("h1", "page-heading", title);
  const intro = element("p", "page-intro", description);
  appElement.append(heading, intro);
  return appElement;
}

function setView(view) {
  currentView = view;
  for (const nav of navButtons) {
    const active = nav.dataset.view === view;
    nav.classList.toggle("active", active);
    if (active) nav.setAttribute("aria-current", "page");
    else nav.removeAttribute("aria-current");
  }
  const renderers = {
    home: renderHome,
    search: renderSearch,
    categories: renderCategories,
    flashcards: renderFlashcards,
    quiz: renderQuizSetup,
    stats: renderStats,
  };
  renderers[view]();
  appElement.focus({ preventScroll: true });
}

function renderHome() {
  appElement.replaceChildren();
  const hero = element("section", "hero");
  hero.append(
    element("div", "eyebrow", "Noongar vocabulary"),
    element("h1", "", "Kaya! Welcome"),
    element("p", "", "Explore the dictionary, practice with flashcards, and test your knowledge at your own pace."),
  );
  appElement.append(hero);

  const strip = element("div", "stats-strip");
  const accuracy = stats.attempted ? `${Math.round(stats.correct / stats.attempted * 100)}%` : "—";
  for (const [value, label] of [
    [vocabulary.length, "Dictionary terms"],
    [categories.length, "Categories"],
    [accuracy, "Quiz accuracy"],
  ]) {
    const card = element("div", "stat-card");
    card.append(element("span", "stat-number", String(value)), element("span", "stat-label", label));
    strip.append(card);
  }
  appElement.append(strip, element("h2", "section-title", "Choose an activity"));

  const actions = [
    ["⌕", "Search Dictionary", "Find a word in English or Noongar.", "search"],
    ["▦", "Browse Categories", "Explore words grouped by topic.", "categories"],
    ["▤", "Browse Flashcards", "Reveal meanings and practice recall.", "flashcards"],
    ["✓", "Interactive Quiz", "Choose a category or the whole dictionary.", "quiz"],
  ];
  const grid = element("div", "action-grid");
  for (const [icon, title, description, view] of actions) {
    const card = button("", () => setView(view), "action-card");
    card.append(element("span", "action-icon", icon), element("span", "action-title", title), element("span", "action-description", description));
    grid.append(card);
  }
  appElement.append(grid);
}

function appendWordRow(container, item, showCategory = true) {
  const row = element("article", "word-row");
  const word = element("div");
  word.append(element("div", "word-noongar", item.noongar), element("div", "word-english", item.english));
  if (showCategory) word.append(element("div", "word-category", item.category));
  row.append(word, createPronounceButton(item.noongar));
  container.append(row);
}

function renderSearch() {
  page(
    "Search Dictionary",
    "Search for words in English or Noongar. Speaker buttons use your device voice; pronunciation may be approximate.",
  );
  const toolbar = element("div", "toolbar");
  const field = element("div", "field");
  const label = element("label", "", "Search words");
  label.htmlFor = "dictionary-search";
  const input = element("input", "input");
  input.id = "dictionary-search";
  input.type = "search";
  input.placeholder = "Try an English or Noongar word";
  input.autocomplete = "off";
  field.append(label, input);
  toolbar.append(field);
  appElement.append(toolbar);
  const summary = element("p", "result-summary", "Enter a word or part of a word to search.");
  const results = element("div", "results-list");
  results.setAttribute("aria-live", "polite");
  appElement.append(summary, results);
  input.addEventListener("input", () => {
    const query = input.value.trim().toLocaleLowerCase();
    results.replaceChildren();
    if (!query) {
      summary.textContent = "Enter a word or part of a word to search.";
      return;
    }
    const matches = vocabulary.filter((item) =>
      item.english.toLocaleLowerCase().includes(query) ||
      item.noongar.toLocaleLowerCase().includes(query)
    );
    summary.textContent = `${matches.length} matching term${matches.length === 1 ? "" : "s"}.`;
    if (!matches.length) results.append(element("div", "empty-state", "No matching words. Try another search."));
    matches.slice(0, 100).forEach((item) => appendWordRow(results, item));
    if (matches.length > 100) results.append(element("p", "result-summary", "Showing the first 100 results. Narrow your search to see more."));
  });
  input.focus();
}

function renderCategories() {
  page("Browse Categories", "Choose a category to browse its Noongar words and English meanings.");
  const grid = element("div", "category-grid");
  for (const category of categories) {
    const count = vocabulary.filter((item) => item.category === category).length;
    const card = button("", () => showCategoryWords(category), "category-card");
    card.append(element("span", "category-name", category), element("span", "category-count", `${count} words`));
    grid.append(card);
  }
  appElement.append(grid);
}

function showCategoryWords(category) {
  page(
    category,
    "Vocabulary in this category. Speaker buttons use your device voice; pronunciation may be approximate.",
  );
  appElement.append(button("← All categories", renderCategories, "button button-secondary"));
  const sortToolbar = element("div", "toolbar");
  const { wrapper: sortWrapper, select: sortSelect } = selectField(
    "Sort words by",
    ["English", "Noongar"],
    "English",
    null,
    "category-word-sort",
  );
  sortToolbar.append(sortWrapper);
  appElement.append(sortToolbar);
  const results = element("div", "results-list");
  results.style.marginTop = "16px";
  results.classList.add("category-word-list");
  const entries = vocabulary.filter((item) => item.category === category);
  function renderEntries() {
    results.replaceChildren();
    const primaryLanguage = sortSelect.value.toLocaleLowerCase();
    const secondaryLanguage = primaryLanguage === "english" ? "noongar" : "english";
    [...entries]
      .sort((left, right) => left[primaryLanguage].localeCompare(right[primaryLanguage], undefined, {
        sensitivity: "base",
      }))
      .forEach((item) => {
        const row = element("article", "word-row category-word-row");
        const words = element("div");
        words.append(
          element("div", "category-word-primary", item[primaryLanguage]),
          element("div", "category-word-secondary", item[secondaryLanguage]),
        );
        row.append(words, createPronounceButton(item.noongar));
        results.append(row);
      });
  }
  sortSelect.addEventListener("change", renderEntries);
  appElement.append(results);
  renderEntries();
}

function renderFlashcards() {
  page(
    "Browse Flashcards",
    "Choose a category, reveal each English meaning, or hear an approximate device-voice pronunciation.",
  );
  const toolbar = element("div", "toolbar");
  const { wrapper, select } = selectField("Card set", [ALL_CATEGORIES, ...categories], ALL_CATEGORIES, null, "flashcard-category");
  toolbar.append(wrapper);
  appElement.append(toolbar);
  const card = element("section", "flashcard");
  const counter = element("div", "flashcard-count");
  const word = element("h2", "flashcard-word");
  const answer = element("div", "flashcard-answer", " ");
  const category = element("div", "flashcard-category", " ");
  const actions = element("div", "card-actions");
  let currentFlashcardWord = "";
  const pronounceButton = button(
    "🔊",
    () => pronounceNoongarWord(currentFlashcardWord),
    "button button-secondary speaker-button",
  );
  pronounceButton.disabled = !(
    "speechSynthesis" in window
    && typeof window.SpeechSynthesisUtterance === "function"
  );
  const revealButton = button("Reveal meaning", () => {
    if (!flashcards.length) return;
    revealed = true;
    answer.textContent = flashcards[flashcardIndex].english;
    category.textContent = flashcards[flashcardIndex].category;
    revealButton.disabled = true;
  });
  const previousButton = button("Previous card", () => {
    if (!flashcards.length) return;
    flashcardIndex = (flashcardIndex - 1 + flashcards.length) % flashcards.length;
    updateFlashcard();
  }, "button button-secondary");
  const nextButton = button("Next card", () => {
    if (!flashcards.length) return;
    flashcardIndex = (flashcardIndex + 1) % flashcards.length;
    updateFlashcard();
  }, "button button-secondary");
  const shuffleButton = button("Shuffle", () => {
    flashcards = shuffle([...flashcards]);
    flashcardIndex = 0;
    updateFlashcard();
  }, "button button-secondary");
  actions.append(previousButton, pronounceButton, revealButton, nextButton, shuffleButton);
  card.append(counter, word, answer, category, actions);
  appElement.append(card);

  function updateFlashcard() {
    if (!flashcards.length) {
      counter.textContent = "No words in this set.";
      word.textContent = "";
      answer.textContent = "";
      category.textContent = "";
      revealButton.disabled = true;
      nextButton.disabled = true;
      pronounceButton.disabled = true;
      return;
    }
    revealed = false;
    const current = flashcards[flashcardIndex];
    currentFlashcardWord = current.noongar;
    pronounceButton.setAttribute(
      "aria-label",
      `Pronounce Noongar word ${current.noongar}`,
    );
    pronounceButton.title = `Play an approximate device-voice pronunciation of ${current.noongar}.`;
    counter.textContent = `Card ${flashcardIndex + 1} of ${flashcards.length}`;
    word.textContent = current.noongar;
    answer.textContent = revealed ? current.english : " ";
    category.textContent = revealed ? current.category : " ";
    revealButton.disabled = revealed;
    pronounceButton.disabled = !(
      "speechSynthesis" in window
      && typeof window.SpeechSynthesisUtterance === "function"
    );
    previousButton.disabled = false;
    nextButton.disabled = false;
  }

  function resetDeck() {
    const selected = select.value;
    const deck = selected === ALL_CATEGORIES
      ? vocabulary
      : vocabulary.filter((item) => item.category === selected);
    flashcards = shuffle([...deck]);
    flashcardIndex = 0;
    revealed = false;
    updateFlashcard();
  }
  select.addEventListener("change", resetDeck);
  resetDeck();
}

function shuffle(items) {
  for (let index = items.length - 1; index > 0; index -= 1) {
    const other = Math.floor(Math.random() * (index + 1));
    [items[index], items[other]] = [items[other], items[index]];
  }
  return items;
}

function renderQuizSetup() {
  page(
    "Interactive Quiz",
    "Choose one category or draw questions from across the whole dictionary. Use the speaker button to hear an approximate pronunciation.",
  );
  const toolbar = element("div", "toolbar");
  const categoryField = selectField("Question set", [ALL_CATEGORIES, ...categories], ALL_CATEGORIES, null, "quiz-category");
  const countWrapper = element("div", "field");
  const countLabel = element("label", "", "Number of questions");
  countLabel.htmlFor = "quiz-count";
  const countInput = element("input", "input");
  countInput.id = "quiz-count";
  countInput.type = "number";
  countInput.min = "1";
  countInput.max = String(vocabulary.length);
  countInput.value = "5";
  countWrapper.append(countLabel, countInput);
  toolbar.append(categoryField.wrapper, countWrapper, button("Start quiz", () => startQuiz(categoryField.select.value, countInput.value)));
  appElement.append(toolbar);
  appElement.append(element("div", "notice", "Category quizzes use answer options from the selected category. Whole-dictionary quizzes use options from the full dictionary."));
}

function startQuiz(category, countValue) {
  const pool = category === ALL_CATEGORIES
    ? vocabulary
    : vocabulary.filter((item) => item.category === category);
  const distinctAnswers = [...new Set(pool.map((item) => item.english.toLocaleLowerCase()))];
  if (distinctAnswers.length < 2) {
    appElement.append(element("div", "error-state", "This set needs at least two different English meanings for a quiz."));
    return;
  }
  const count = Number.parseInt(countValue, 10);
  if (!Number.isInteger(count) || count < 1) {
    appElement.append(element("div", "error-state", "Enter a valid number of questions."));
    return;
  }
  quiz = {
    questions: shuffle([...pool]).slice(0, count),
    pool,
    category,
    index: 0,
    correct: 0,
    attempted: 0,
    answered: false,
  };
  renderQuizQuestion();
}

function renderQuizQuestion() {
  const existing = document.querySelector("#quiz-run");
  if (existing) existing.remove();
  const run = element("section");
  run.id = "quiz-run";
  run.style.marginTop = "26px";
  appElement.append(run);

  if (quiz.index >= quiz.questions.length) {
    run.append(element("div", "question-card"));
    const resultCard = run.firstElementChild;
    resultCard.append(
      element("h2", "section-title", "Quiz complete"),
      element(
        "p",
        "",
        `You answered ${quiz.correct} of ${quiz.questions.length} question${quiz.questions.length === 1 ? "" : "s"} correctly.`,
      ),
      button("Try another quiz", renderQuizSetup, "button button-secondary"),
    );
    return;
  }

  quiz.answered = false;
  const question = quiz.questions[quiz.index];
  const progress = element("div", "quiz-progress");
  const progressValue = element("span");
  progressValue.style.width = `${quiz.index / quiz.questions.length * 100}%`;
  progress.append(progressValue);
  const card = element("div", "question-card");
  card.append(
    element("div", "question-count", `Question ${quiz.index + 1} of ${quiz.questions.length}`),
    element("h2", "question-word", `What is the English meaning of “${question.noongar}”?`),
    createPronounceButton(question.noongar),
    element("p", "word-category", question.category),
  );
  const correctKey = question.english.toLocaleLowerCase();
  const optionPool = quiz.category === ALL_CATEGORIES
    ? quiz.pool
    : quiz.pool.filter((item) => item.category === quiz.category);
  const distractors = [...new Map(
    optionPool
      .filter((item) => item.english.toLocaleLowerCase() !== correctKey)
      .map((item) => [item.english.toLocaleLowerCase(), item.english]),
  ).values()];
  const options = shuffle([...shuffle(distractors).slice(0, 3), question.english]);
  const answers = element("div", "answer-list");
  const feedback = element("div", "feedback");
  const submit = button("Submit answer", () => {
    if (quiz.answered) return;
    const selected = answers.querySelector("input:checked");
    if (!selected) {
      feedback.textContent = "Choose an answer before submitting.";
      feedback.className = "feedback incorrect";
      return;
    }
    quiz.answered = true;
    quiz.attempted += 1;
    stats.attempted += 1;
    if (selected.value.toLocaleLowerCase() === correctKey) {
      quiz.correct += 1;
      stats.correct += 1;
      feedback.textContent = "Correct! Well done.";
      feedback.className = "feedback correct";
    } else {
      feedback.textContent = `Not quite. The answer is: ${question.english}`;
      feedback.className = "feedback incorrect";
    }
    submit.textContent = "Next question";
    submit.onclick = () => {
      quiz.index += 1;
      renderQuizQuestion();
    };
  });
  for (const [index, option] of options.entries()) {
    const label = element("label", "answer-option");
    const input = element("input");
    input.type = "radio";
    input.name = "quiz-answer";
    input.value = option;
    input.id = `answer-${index}`;
    label.htmlFor = input.id;
    label.append(input, element("span", "", option));
    answers.append(label);
  }
  card.append(answers, feedback, submit);
  run.append(progress, card);
}

function renderStats() {
  page("Session Statistics", "Quiz results are kept only while this page is open.");
  const accuracy = stats.attempted
    ? `${(stats.correct / stats.attempted * 100).toFixed(1)}%`
    : "Not available yet";
  const strip = element("div", "stats-strip");
  for (const [value, label] of [
    [stats.attempted, "Questions attempted"],
    [stats.correct, "Correct answers"],
    [accuracy, "Accuracy"],
  ]) {
    const card = element("div", "stat-card");
    card.append(element("span", "stat-number", String(value)), element("span", "stat-label", label));
    strip.append(card);
  }
  appElement.append(strip);
  if (stats.attempted) {
    appElement.append(button("Reset statistics", () => {
      if (!window.confirm("Reset your quiz statistics for this visit?")) return;
      stats.attempted = 0;
      stats.correct = 0;
      renderStats();
    }, "button button-secondary"));
  }
}

for (const nav of navButtons) {
  nav.addEventListener("click", () => setView(nav.dataset.view));
}

async function startApp() {
  try {
    const response = await fetch(CSV_URL);
    if (!response.ok) {
      throw new Error(`Could not load the dictionary data (HTTP ${response.status}).`);
    }
    vocabulary = readDictionary(await response.text());
    if (!vocabulary.length) throw new Error("The dictionary has no usable vocabulary rows.");
    categories = [...new Set(vocabulary.map((item) => item.category))].sort((a, b) => a.localeCompare(b));
    statusElement.textContent = `${vocabulary.length} terms · ${categories.length} categories`;
    setView(currentView);
  } catch (error) {
    statusElement.textContent = "Dictionary could not be loaded";
    appElement.replaceChildren(
      element("h1", "page-heading", "Dictionary unavailable"),
      element("div", "error-state", `${error.message} Make sure the web app and “Noongar categories.csv” are hosted in the same folder, then open the app through an HTTPS web address or a local web server.`),
    );
  }
}

window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallPrompt = event;
  document.querySelector("#install-button").hidden = false;
});

document.querySelector("#install-button").addEventListener("click", async () => {
  if (!deferredInstallPrompt) return;
  deferredInstallPrompt.prompt();
  await deferredInstallPrompt.userChoice;
  deferredInstallPrompt = null;
  document.querySelector("#install-button").hidden = true;
});

if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost")) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("./service-worker.js").catch((error) => {
      console.error("Could not register offline support:", error);
    });
  });
}

startApp();
