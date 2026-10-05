import csv
import hashlib
import json
import random
import shutil
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk


APP_TITLE = "Noongar Language Learning"
ALL_CATEGORIES = "All categories"
BLACK = "#101010"
BLACK_SOFT = "#1D1D1D"
RED = "#FF3347"
RED_DARK = "#9F1026"
YELLOW = "#FFD100"
TEXT = "#F7F4E9"
MUTED_TEXT = "#CCC6B8"
LINE = "#49443B"


def find_dictionary_file():
    if getattr(sys, "frozen", False):
        bundled_path = Path(sys._MEIPASS) / "Noongar categories.csv"
        if bundled_path.is_file():
            return bundled_path
    return Path(__file__).resolve().parent / "Noongar categories.csv"


def load_vocabulary(csv_path):
    vocabulary = []
    with csv_path.open(mode="r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        if not reader.fieldnames:
            raise ValueError("The dictionary CSV has no header row.")

        normalized_headers = {
            (header or "").strip().casefold(): header
            for header in reader.fieldnames
        }
        if "noongar" not in normalized_headers or "english" not in normalized_headers:
            raise ValueError(
                "The dictionary CSV must have 'Noongar' and 'English' columns."
            )
        category_header = normalized_headers.get("category")

        for row in reader:
            noongar_word = (
                row.get(normalized_headers["noongar"]) or ""
            ).strip()
            english_word = (
                row.get(normalized_headers["english"]) or ""
            ).strip()
            category = (
                (row.get(category_header) or "").strip()
                if category_header
                else ""
            )
            if noongar_word and english_word:
                vocabulary.append(
                    {
                        "noongar": noongar_word,
                        "english": english_word,
                        "category": category or "Uncategorised",
                    }
                )
    return vocabulary


def find_pronunciation_directory():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "audio"
    return Path(__file__).resolve().parent / "web" / "audio"


def load_pronunciation_files(audio_directory):
    manifest_path = audio_directory / "manifest.json"
    if not manifest_path.is_file():
        return {}
    with manifest_path.open(encoding="utf-8") as manifest_file:
        manifest = json.load(manifest_file)
    files = manifest.get("files")
    if not isinstance(files, dict):
        raise ValueError("The pronunciation audio manifest has an invalid format.")
    for word, filename in files.items():
        expected_name = f"{hashlib.sha256(word.encode('utf-8')).hexdigest()}.wav"
        if filename != expected_name:
            raise ValueError(
                f"The pronunciation audio entry for '{word}' has an invalid filename."
            )
    return files


class NoongarApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1050x720")
        self.root.minsize(800, 580)

        try:
            self.vocab = load_vocabulary(find_dictionary_file())
            self.pronunciation_audio_directory = find_pronunciation_directory()
            self.pronunciation_files = load_pronunciation_files(
                self.pronunciation_audio_directory
            )
        except (OSError, ValueError) as error:
            messagebox.showerror("Could not load dictionary", str(error), parent=root)
            root.destroy()
            return

        self.categories = sorted(
            {item["category"] for item in self.vocab},
            key=str.casefold,
        )
        self.total_quiz_questions = 0
        self.correct_answers = 0
        self.speech_process = None
        self.content = None
        self.configure_style()
        self.build_shell()
        self.show_home()

    def configure_style(self):
        self.root.configure(bg=BLACK)
        self.root.option_add("*Button.background", YELLOW)
        self.root.option_add("*Button.foreground", BLACK)
        self.root.option_add("*Button.activeBackground", YELLOW)
        self.root.option_add("*Button.activeForeground", BLACK)
        self.root.option_add("*Button.highlightBackground", YELLOW)
        self.root.option_add("*Label.background", BLACK)
        self.root.option_add("*Label.foreground", TEXT)
        self.root.option_add("*Radiobutton.background", BLACK)
        self.root.option_add("*Radiobutton.foreground", TEXT)
        self.root.option_add("*Radiobutton.activeBackground", BLACK)
        self.root.option_add("*Radiobutton.activeForeground", YELLOW)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            background=BLACK_SOFT,
            fieldbackground=BLACK_SOFT,
            foreground=TEXT,
            rowheight=30,
            font=("Helvetica", 11),
        )
        style.map(
            "Treeview",
            background=[("selected", RED)],
            foreground=[("selected", BLACK)],
        )
        style.configure(
            "Treeview.Heading",
            background=BLACK,
            foreground=TEXT,
            font=("Helvetica", 11, "bold"),
        )
        style.map(
            "Treeview.Heading",
            background=[("active", RED_DARK)],
            foreground=[("active", TEXT)],
        )
        style.configure(
            "TCombobox",
            fieldbackground=BLACK_SOFT,
            background=RED,
            foreground=TEXT,
            arrowcolor=BLACK,
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", BLACK_SOFT)],
            foreground=[("readonly", TEXT)],
            selectbackground=[("readonly", RED)],
            selectforeground=[("readonly", BLACK)],
        )
        style.configure(
            "TEntry",
            fieldbackground=BLACK_SOFT,
            foreground=TEXT,
            insertcolor=YELLOW,
        )
        style.configure(
            "TSpinbox",
            fieldbackground=BLACK_SOFT,
            background=RED,
            foreground=TEXT,
            arrowcolor=BLACK,
        )
        style.configure(
            "Vertical.TScrollbar",
            background=RED,
            troughcolor=BLACK,
            arrowcolor=BLACK,
        )

    def build_shell(self):
        shell = tk.Frame(self.root, bg=BLACK)
        shell.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(shell, bg=BLACK, width=220)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)
        sidebar.pack_propagate(False)
        tk.Label(
            sidebar,
            text="Noongar\nLanguage\nLearning",
            bg=BLACK,
            fg=TEXT,
            font=("Helvetica", 15, "bold"),
            justify=tk.LEFT,
            wraplength=176,
        ).pack(anchor=tk.W, padx=22, pady=(28, 30))

        navigation = [
            ("Home", self.show_home),
            ("Search Dictionary", self.show_search),
            ("Browse Flashcards", self.show_flashcards),
            ("Browse Categories", self.show_categories),
            ("Interactive Quiz", self.show_quiz),
            ("Session Statistics", self.show_stats),
        ]
        for label, command in navigation:
            tk.Button(
                sidebar,
                text=label,
                command=command,
                anchor=tk.W,
                bg=YELLOW,
                fg=BLACK,
                activebackground=YELLOW,
                activeforeground=BLACK,
                relief=tk.FLAT,
                padx=20,
                pady=12,
                font=("Helvetica", 12),
            ).pack(fill=tk.X, padx=10, pady=3)

        tk.Label(
            sidebar,
            text=f"{len(self.vocab)} dictionary terms",
            bg=BLACK,
            fg=MUTED_TEXT,
            font=("Helvetica", 10),
        ).pack(side=tk.BOTTOM, anchor=tk.W, padx=22, pady=20)

        self.content = tk.Frame(shell, bg=BLACK)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def speak_noongar(self, word):
        filename = self.pronunciation_files.get(word)
        if filename:
            audio_path = self.pronunciation_audio_directory / filename
            executable = shutil.which("afplay")
            if not audio_path.is_file():
                messagebox.showerror(
                    "Pronunciation audio unavailable",
                    f"The generated audio file for '{word}' could not be found.",
                    parent=self.root,
                )
                return
            if executable is None:
                messagebox.showerror(
                    "Audio playback unavailable",
                    "This device does not have the macOS audio player available.",
                    parent=self.root,
                )
                return
            if self.speech_process and self.speech_process.poll() is None:
                self.speech_process.terminate()
            try:
                self.speech_process = subprocess.Popen(
                    [executable, str(audio_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                )
            except OSError as error:
                messagebox.showerror(
                    "Could not play pronunciation",
                    str(error),
                    parent=self.root,
                )
                return
            self.root.after(
                100,
                self.check_speech_process,
                self.speech_process,
                word,
            )
            return

        executable = shutil.which("say")
        if executable is None:
            messagebox.showerror(
                "Speech unavailable",
                "This device does not have the macOS speech command available.",
                parent=self.root,
            )
            return
        if self.speech_process and self.speech_process.poll() is None:
            self.speech_process.terminate()
        try:
            self.speech_process = subprocess.Popen(
                [executable, "-v", "Karen", "-r", "130", word],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError as error:
            messagebox.showerror(
                "Could not pronounce word",
                str(error),
                parent=self.root,
            )
            return
        self.root.after(
            100,
            self.check_speech_process,
            self.speech_process,
            word,
        )

    def check_speech_process(self, process, word):
        if self.speech_process is not process:
            return
        if process.poll() is None:
            self.root.after(100, self.check_speech_process, process, word)
            return
        if process.returncode:
            error = process.stderr.read().strip() if process.stderr else ""
            messagebox.showerror(
                "Could not pronounce word",
                error or f"The device voice could not pronounce '{word}'.",
                parent=self.root,
            )

    def page_heading(self, title, subtitle=""):
        self.clear_content()
        tk.Label(
            self.content,
            text=title,
            bg=BLACK,
            fg=TEXT,
            font=("Helvetica", 25, "bold"),
        ).pack(anchor=tk.W, padx=30, pady=(28, 4))
        if subtitle:
            tk.Label(
                self.content,
                text=subtitle,
                bg=BLACK,
                fg=MUTED_TEXT,
                font=("Helvetica", 12),
            ).pack(anchor=tk.W, padx=32, pady=(0, 18))

    def show_home(self):
        self.page_heading(
            "Kaya! Welcome",
            "Choose an activity to explore the Noongar dictionary.",
        )
        cards = [
            ("Search Dictionary", self.show_search),
            ("Browse Flashcards", self.show_flashcards),
            ("Browse Categories", self.show_categories),
            ("Interactive Quiz", self.show_quiz),
        ]
        card_area = tk.Frame(self.content, bg=BLACK)
        card_area.pack(fill=tk.BOTH, expand=True, padx=22, pady=10)
        for index, (label, command) in enumerate(cards):
            button = tk.Button(
                card_area,
                text=label,
                command=command,
                bg=YELLOW,
                fg=BLACK,
                activebackground=YELLOW,
                activeforeground=BLACK,
                relief=tk.GROOVE,
                borderwidth=1,
                font=("Helvetica", 16, "bold"),
                width=24,
                height=4,
            )
            button.grid(
                row=index // 2,
                column=index % 2,
                padx=12,
                pady=12,
                sticky="nsew",
            )
        for row in range(2):
            card_area.rowconfigure(row, weight=1)
        for column in range(2):
            card_area.columnconfigure(column, weight=1)

    def make_results_table(self, parent):
        frame = tk.Frame(parent, bg=BLACK)
        frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(8, 25))
        columns = ("noongar", "english", "category")
        table = ttk.Treeview(frame, columns=columns, show="headings")
        table.heading("noongar", text="Noongar")
        table.heading("english", text="English")
        table.heading("category", text="Category")
        table.column("noongar", width=220)
        table.column("english", width=300)
        table.column("category", width=230)
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        return table

    def show_search(self):
        self.page_heading(
            "Search Dictionary",
            "Search by English or Noongar word. Select a result, then use its device-voice pronunciation.",
        )
        query = tk.StringVar()
        search_entry = ttk.Entry(self.content, textvariable=query, width=45)
        search_entry.pack(anchor=tk.W, padx=30, pady=(0, 8))
        speak_button = tk.Button(
            self.content,
            text="Speak selected Noongar word",
            command=lambda: self.speak_selected_search_result(table),
            state=tk.DISABLED,
            padx=12,
            pady=6,
        )
        speak_button.pack(anchor=tk.W, padx=30, pady=(0, 8))
        table = self.make_results_table(self.content)

        def update_speak_button(event):
            speak_button.configure(
                state=tk.NORMAL if event.widget.selection() else tk.DISABLED
            )

        table.bind("<<TreeviewSelect>>", update_speak_button)

        def update_results(*_):
            value = query.get().strip().casefold()
            table.delete(*table.get_children())
            speak_button.configure(state=tk.DISABLED)
            if not value:
                return
            matches = [
                item
                for item in self.vocab
                if value in item["noongar"].casefold()
                or value in item["english"].casefold()
            ]
            for item in matches:
                table.insert(
                    "",
                    tk.END,
                    values=(item["noongar"], item["english"], item["category"]),
                )

        query.trace_add("write", update_results)
        search_entry.focus_set()

    def speak_selected_search_result(self, table):
        selected = table.selection()
        if selected:
            values = table.item(selected[0], "values")
            if values:
                self.speak_noongar(str(values[0]))

    def show_categories(self):
        self.page_heading(
            "Browse Categories",
            "Choose a category to review its vocabulary. Click an underlined Noongar word for an approximate device-voice pronunciation.",
        )
        selected = tk.StringVar(value=self.categories[0] if self.categories else "")
        selector = ttk.Combobox(
            self.content,
            textvariable=selected,
            values=self.categories,
            state="readonly",
            width=40,
        )
        selector.pack(anchor=tk.W, padx=30, pady=(0, 8))
        sort_by = tk.StringVar(value="English")
        sort_controls = tk.Frame(self.content, bg=BLACK)
        sort_controls.pack(anchor=tk.W, padx=30, pady=(0, 8))
        tk.Label(
            sort_controls,
            text="Sort words by:",
            bg=BLACK,
            fg=TEXT,
        ).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Combobox(
            sort_controls,
            textvariable=sort_by,
            values=("English", "Noongar"),
            state="readonly",
            width=18,
        ).pack(side=tk.LEFT)
        results_frame = tk.Frame(self.content, bg=BLACK)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(8, 25))
        results = tk.Text(
            results_frame,
            bg=BLACK_SOFT,
            fg=TEXT,
            insertbackground=YELLOW,
            font=("Helvetica", 12),
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=16,
            pady=12,
            spacing1=5,
            spacing3=14,
            state=tk.DISABLED,
        )
        results.tag_configure("primary", font=("Helvetica", 12, "bold"))
        results.tag_configure("secondary", font=("Helvetica", 12))
        scrollbar = ttk.Scrollbar(
            results_frame,
            orient=tk.VERTICAL,
            command=results.yview,
        )
        results.configure(yscrollcommand=scrollbar.set)
        results.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def show_entries(event=None):
            category = event.widget.get() if event else selected.get()
            primary = "english" if sort_by.get() == "English" else "noongar"
            secondary = "noongar" if primary == "english" else "english"
            entries = sorted(
                (item for item in self.vocab if item["category"] == category),
                key=lambda item: item[primary].casefold(),
            )
            results.configure(state=tk.NORMAL)
            results.delete("1.0", tk.END)
            for index, item in enumerate(entries):
                pronunciation_tag = f"pronounce-{index}"
                results.tag_configure(
                    pronunciation_tag,
                    foreground=TEXT,
                    underline=True,
                )
                results.tag_bind(
                    pronunciation_tag,
                    "<Button-1>",
                    lambda event, word=item["noongar"]: self.speak_clicked_word(
                        event,
                        word,
                    ),
                )
                results.tag_bind(
                    pronunciation_tag,
                    "<Enter>",
                    lambda event: event.widget.configure(cursor="hand2"),
                )
                results.tag_bind(
                    pronunciation_tag,
                    "<Leave>",
                    lambda event: event.widget.configure(cursor="xterm"),
                )
                primary_tags = (
                    ("primary", pronunciation_tag)
                    if primary == "noongar"
                    else ("primary",)
                )
                secondary_tags = (
                    ("secondary", pronunciation_tag)
                    if secondary == "noongar"
                    else ("secondary",)
                )
                results.insert(tk.END, f'{item[primary]}\n', primary_tags)
                results.insert(tk.END, f'{item[secondary]}\n\n', secondary_tags)
            results.configure(state=tk.DISABLED)

        selector.bind("<<ComboboxSelected>>", show_entries)
        sort_by.trace_add("write", show_entries)
        show_entries()

    def speak_clicked_word(self, event, word):
        event.widget.focus_set()
        self.speak_noongar(word)
        return "break"

    def show_flashcards(self):
        self.page_heading(
            "Browse Flashcards",
            "Reveal the English meaning, hear an approximate device-voice pronunciation, then move through the deck.",
        )
        if not self.vocab:
            tk.Label(self.content, text="No vocabulary entries are available.").pack()
            return
        self.flashcards = self.vocab.copy()
        random.shuffle(self.flashcards)
        self.flashcard_index = 0
        self.flashcard_revealed = False
        self.flashcard_counter = tk.StringVar()
        self.flashcard_word = tk.StringVar()
        self.flashcard_answer = tk.StringVar()
        self.flashcard_feedback = tk.StringVar()
        card = tk.Frame(
            self.content,
            bg=BLACK_SOFT,
            highlightbackground=LINE,
            highlightthickness=1,
        )
        card.pack(fill=tk.BOTH, expand=True, padx=70, pady=30)
        tk.Label(
            card,
            textvariable=self.flashcard_counter,
            bg=BLACK_SOFT,
            fg=MUTED_TEXT,
            font=("Helvetica", 12),
        ).pack(pady=(30, 15))
        tk.Label(
            card,
            textvariable=self.flashcard_word,
            bg=BLACK_SOFT,
            fg=TEXT,
            font=("Helvetica", 32, "bold"),
            wraplength=650,
        ).pack(pady=35)
        tk.Label(
            card,
            textvariable=self.flashcard_answer,
            bg=BLACK_SOFT,
            fg=TEXT,
            font=("Helvetica", 20),
        ).pack(pady=10)
        tk.Label(
            card,
            textvariable=self.flashcard_feedback,
            bg=BLACK_SOFT,
            fg=MUTED_TEXT,
            font=("Helvetica", 11),
        ).pack(pady=5)
        controls = tk.Frame(card, bg=BLACK_SOFT)
        controls.pack(pady=25)
        tk.Button(
            controls,
            text="Speak word",
            command=lambda: self.speak_noongar(
                self.flashcards[self.flashcard_index]["noongar"]
            ),
            padx=15,
            pady=8,
        ).pack(side=tk.LEFT, padx=8)
        tk.Button(
            controls,
            text="Previous card",
            command=self.previous_flashcard,
            padx=15,
            pady=8,
        ).pack(side=tk.LEFT, padx=8)
        tk.Button(
            controls,
            text="Reveal meaning",
            command=self.reveal_flashcard,
            padx=15,
            pady=8,
        ).pack(side=tk.LEFT, padx=8)
        tk.Button(
            controls,
            text="Next card",
            command=self.next_flashcard,
            padx=15,
            pady=8,
        ).pack(side=tk.LEFT, padx=8)
        self.update_flashcard()

    def update_flashcard(self):
        card = self.flashcards[self.flashcard_index]
        self.flashcard_counter.set(
            f"Card {self.flashcard_index + 1} of {len(self.flashcards)}"
        )
        self.flashcard_word.set(card["noongar"])
        self.flashcard_answer.set("")
        self.flashcard_feedback.set("")
        self.flashcard_revealed = False

    def reveal_flashcard(self):
        if not self.flashcard_revealed:
            card = self.flashcards[self.flashcard_index]
            self.flashcard_answer.set(card["english"])
            self.flashcard_feedback.set(card["category"])
            self.flashcard_revealed = True

    def next_flashcard(self):
        self.flashcard_index = (self.flashcard_index + 1) % len(self.flashcards)
        self.update_flashcard()

    def previous_flashcard(self):
        self.flashcard_index = (self.flashcard_index - 1) % len(self.flashcards)
        self.update_flashcard()

    def show_quiz(self):
        self.page_heading(
            "Interactive Quiz",
            "Choose a category or quiz across the whole dictionary.",
        )
        if len(self.vocab) < 2:
            tk.Label(
                self.content,
                text="At least two vocabulary entries are required for a quiz.",
            ).pack(anchor=tk.W, padx=30)
            return

        setup = tk.Frame(self.content, bg=BLACK)
        setup.pack(anchor=tk.W, padx=30, pady=(0, 12))
        tk.Label(setup, text="Question set:", bg=BLACK, fg=TEXT).grid(
            row=0, column=0, sticky=tk.W, pady=6
        )
        self.quiz_category = tk.StringVar(value=ALL_CATEGORIES)
        ttk.Combobox(
            setup,
            textvariable=self.quiz_category,
            values=[ALL_CATEGORIES, *self.categories],
            state="readonly",
            width=35,
        ).grid(row=0, column=1, sticky=tk.W, padx=10)
        tk.Label(setup, text="Number of questions:", bg=BLACK, fg=TEXT).grid(
            row=1, column=0, sticky=tk.W, pady=6
        )
        self.quiz_count = tk.StringVar(value="5")
        ttk.Spinbox(
            setup,
            from_=1,
            to=len(self.vocab),
            textvariable=self.quiz_count,
            width=8,
        ).grid(row=1, column=1, sticky=tk.W, padx=10)
        tk.Button(
            setup,
            text="Start quiz",
            command=self.start_quiz,
            padx=12,
            pady=6,
        ).grid(row=2, column=1, sticky=tk.W, padx=10, pady=8)

        self.quiz_area = tk.Frame(self.content, bg=BLACK)
        self.quiz_area.pack(fill=tk.BOTH, expand=True, padx=30, pady=10)

    def start_quiz(self):
        if self.quiz_category.get() == ALL_CATEGORIES:
            pool = self.vocab
        else:
            pool = [
                item
                for item in self.vocab
                if item["category"] == self.quiz_category.get()
            ]
        if len({item["english"].casefold() for item in pool}) < 2:
            messagebox.showerror(
                "Not enough answers",
                "This question set needs at least two different English meanings.",
                parent=self.root,
            )
            return
        self.quiz_pool = pool
        try:
            question_count = int(self.quiz_count.get())
        except ValueError:
            messagebox.showerror(
                "Invalid number",
                "Enter a whole number of questions.",
                parent=self.root,
            )
            return
        if question_count < 1:
            messagebox.showerror(
                "Invalid number",
                "Choose at least one question.",
                parent=self.root,
            )
            return
        self.quiz_questions = random.sample(pool, min(question_count, len(pool)))
        self.quiz_index = 0
        self.quiz_correct = 0
        self.show_quiz_question()

    def show_quiz_question(self):
        for child in self.quiz_area.winfo_children():
            child.destroy()
        if self.quiz_index >= len(self.quiz_questions):
            self.show_quiz_result()
            return

        question = self.quiz_questions[self.quiz_index]
        option_pool = self.quiz_pool
        if self.quiz_category.get() != ALL_CATEGORIES:
            option_pool = [
                item
                for item in option_pool
                if item["category"] == self.quiz_category.get()
            ]
        answers = {
            item["english"].casefold(): item["english"]
            for item in option_pool
        }
        wrong_answers = [
            answer
            for key, answer in answers.items()
            if key != question["english"].casefold()
        ]
        options = random.sample(wrong_answers, min(3, len(wrong_answers)))
        options.append(question["english"])
        random.shuffle(options)
        self.quiz_answer = tk.StringVar(value="")

        tk.Label(
            self.quiz_area,
            text=f"Question {self.quiz_index + 1} of {len(self.quiz_questions)}",
            bg=BLACK,
            fg=MUTED_TEXT,
            font=("Helvetica", 12),
        ).pack(anchor=tk.W, pady=(8, 14))
        tk.Label(
            self.quiz_area,
            text=f"What is the English meaning of '{question['noongar']}'?",
            bg=BLACK,
            fg=TEXT,
            font=("Helvetica", 20, "bold"),
            wraplength=680,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=8)
        tk.Button(
            self.quiz_area,
            text="Speak Noongar word",
            command=lambda: self.speak_noongar(question["noongar"]),
            padx=12,
            pady=6,
        ).pack(anchor=tk.W, pady=(0, 8))
        tk.Label(
            self.quiz_area,
            text=question["category"],
            bg=BLACK,
            fg=MUTED_TEXT,
            font=("Helvetica", 11),
        ).pack(anchor=tk.W, pady=(0, 12))
        for option in options:
            tk.Radiobutton(
                self.quiz_area,
                text=option,
                variable=self.quiz_answer,
                value=option,
                bg=BLACK,
                fg=TEXT,
                selectcolor=BLACK_SOFT,
                activebackground=BLACK,
                activeforeground=YELLOW,
                font=("Helvetica", 13),
                anchor=tk.W,
            ).pack(anchor=tk.W, pady=4)
        self.quiz_feedback = tk.StringVar()
        tk.Label(
            self.quiz_area,
            textvariable=self.quiz_feedback,
            bg=BLACK,
            font=("Helvetica", 12, "bold"),
        ).pack(anchor=tk.W, pady=12)
        tk.Button(
            self.quiz_area,
            text="Submit answer",
            command=self.submit_quiz_answer,
            padx=12,
            pady=7,
        ).pack(anchor=tk.W)

    def submit_quiz_answer(self):
        selected = self.quiz_answer.get()
        if not selected:
            messagebox.showinfo(
                "Choose an answer",
                "Select an option before submitting.",
                parent=self.root,
            )
            return
        question = self.quiz_questions[self.quiz_index]
        self.total_quiz_questions += 1
        if selected.casefold() == question["english"].casefold():
            self.correct_answers += 1
            self.quiz_correct += 1
            self.quiz_feedback.set("Correct! Well done.")
        else:
            self.quiz_feedback.set(
                f"Not quite. The answer is: {question['english']}"
            )
        for child in self.quiz_area.winfo_children():
            if isinstance(child, tk.Button):
                child.destroy()
        tk.Button(
            self.quiz_area,
            text="Next question",
            command=self.advance_quiz,
            padx=12,
            pady=7,
        ).pack(anchor=tk.W)

    def advance_quiz(self):
        self.quiz_index += 1
        self.show_quiz_question()

    def show_quiz_result(self):
        tk.Label(
            self.quiz_area,
            text="Quiz complete",
            bg=BLACK,
            fg=TEXT,
            font=("Helvetica", 22, "bold"),
        ).pack(anchor=tk.W, pady=12)
        tk.Label(
            self.quiz_area,
            text=f"You answered {self.quiz_correct} of "
            f"{len(self.quiz_questions)} questions correctly.",
            bg=BLACK,
            font=("Helvetica", 14),
        ).pack(anchor=tk.W, pady=5)
        tk.Button(
            self.quiz_area,
            text="Try another quiz",
            command=self.show_quiz,
            padx=12,
            pady=7,
        ).pack(anchor=tk.W, pady=15)

    def show_stats(self):
        self.page_heading(
            "Session Statistics",
            "Your results for this session.",
        )
        accuracy = (
            f"{self.correct_answers / self.total_quiz_questions * 100:.1f}%"
            if self.total_quiz_questions
            else "N/A"
        )
        stats = [
            ("Total dictionary words", str(len(self.vocab))),
            ("Questions attempted", str(self.total_quiz_questions)),
            ("Correct answers", str(self.correct_answers)),
            ("Accuracy rate", accuracy),
        ]
        for label, value in stats:
            row = tk.Frame(
                self.content,
                bg=BLACK_SOFT,
                highlightbackground=LINE,
                highlightthickness=1,
                padx=18,
                pady=15,
            )
            row.pack(fill=tk.X, padx=30, pady=6)
            tk.Label(
                row,
                text=label,
                bg=BLACK_SOFT,
                fg=MUTED_TEXT,
                font=("Helvetica", 13),
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=value,
                bg=BLACK_SOFT,
                fg=TEXT,
                font=("Helvetica", 14, "bold"),
            ).pack(side=tk.RIGHT)


if __name__ == "__main__":
    root = tk.Tk()
    app = NoongarApp(root)
    if root.winfo_exists():
        root.mainloop()
