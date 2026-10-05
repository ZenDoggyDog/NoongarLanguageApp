import json
import random
import shutil
import subprocess
import sys
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import messagebox, ttk

from noongar_data import (
    build_quiz_options,
    clean_daily_accuracy,
    load_vocabulary,
    record_daily_accuracy,
    search_vocabulary,
    summarize_categories,
)


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
DISCLAIMER = (
    "The intention is education. I acknowledge that words may be spelled or "
    "spoken differently across families, regions and other resources."
)


def word_key(item):
    return f"{item['noongar']}\0{item['english']}"


def find_dictionary_file():
    if getattr(sys, "frozen", False):
        bundled_path = Path(sys._MEIPASS) / "Noongar categories.csv"
        if bundled_path.is_file():
            return bundled_path
    return Path(__file__).resolve().parent / "Noongar categories.csv"


class NoongarApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1050x720")
        self.root.minsize(800, 580)

        try:
            self.vocab = load_vocabulary(find_dictionary_file())
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
        self.daily_accuracy = {}
        self.reviewed_words = set()
        self.missed_words = set()
        self.saved_words = set()
        self.word_lists = {}
        self.font_scale = 100
        self.app_fonts = {}
        self.default_font = tkfont.nametofont("TkDefaultFont", root)
        self.default_font_size = abs(int(self.default_font.cget("size")))
        self.study_data_path = Path.home() / ".noongar-language-learner.json"
        self.load_study_data()
        self.apply_font_scale()
        self.speech_process = None
        self.content = None
        self.configure_style()
        self.build_shell()
        self.show_home()

    def load_study_data(self):
        if not self.study_data_path.exists():
            return
        known_words = {word_key(item) for item in self.vocab}
        try:
            with self.study_data_path.open(encoding="utf-8") as data_file:
                stored = json.load(data_file)
            if not isinstance(stored, dict):
                raise ValueError("Saved study data must be a JSON object.")
            attempted = stored.get("attempted", 0)
            correct = stored.get("correct", 0)
            self.total_quiz_questions = (
                attempted if isinstance(attempted, int) and attempted >= 0 else 0
            )
            self.correct_answers = (
                min(correct, self.total_quiz_questions)
                if isinstance(correct, int) and correct >= 0
                else 0
            )
            self.daily_accuracy = clean_daily_accuracy(
                stored.get("daily_accuracy", {})
            )
            for attribute in ("reviewed_words", "missed_words", "saved_words"):
                stored_name = {
                    "reviewed_words": "reviewed",
                    "missed_words": "missed",
                    "saved_words": "saved",
                }[attribute]
                values = stored.get(stored_name, [])
                if isinstance(values, list):
                    setattr(
                        self,
                        attribute,
                        {value for value in values if isinstance(value, str) and value in known_words},
                    )
            lists = stored.get("lists", {})
            if isinstance(lists, dict):
                self.word_lists = {
                    name: {
                        value
                        for value in values
                        if isinstance(value, str)
                        and value in known_words
                        and value in self.saved_words
                    }
                    for name, values in lists.items()
                    if isinstance(name, str)
                    and name.strip()
                    and isinstance(values, list)
                }
            scale = stored.get("font_scale", 100)
            if isinstance(scale, int):
                self.font_scale = min(130, max(80, scale))
        except (OSError, json.JSONDecodeError, ValueError) as error:
            messagebox.showerror(
                "Could not load saved progress",
                f"Saved study data could not be loaded: {error}",
                parent=self.root,
            )

    def save_study_data(self):
        data = {
            "attempted": self.total_quiz_questions,
            "correct": self.correct_answers,
            "daily_accuracy": self.daily_accuracy,
            "reviewed": sorted(self.reviewed_words),
            "missed": sorted(self.missed_words),
            "saved": sorted(self.saved_words),
            "lists": {
                name: sorted(words) for name, words in self.word_lists.items()
            },
            "font_scale": self.font_scale,
        }
        try:
            with self.study_data_path.open("w", encoding="utf-8") as data_file:
                json.dump(data, data_file, ensure_ascii=False, indent=2)
        except OSError as error:
            messagebox.showerror(
                "Could not save progress",
                f"Your changes could not be saved on this device: {error}",
                parent=self.root,
            )

    def apply_font_scale(self):
        self.default_font.configure(
            size=max(1, round(self.default_font_size * self.font_scale / 100))
        )
        for (size, weight), font in self.app_fonts.items():
            font.configure(
                size=max(1, round(size * self.font_scale / 100)),
                weight=weight,
            )

    def app_font(self, size, weight="normal"):
        key = (size, weight)
        if key not in self.app_fonts:
            self.app_fonts[key] = tkfont.Font(
                root=self.root,
                family="Helvetica",
                size=max(1, round(size * self.font_scale / 100)),
                weight=weight,
            )
        return self.app_fonts[key]

    def adjust_font_scale(self, amount):
        self.font_scale = min(130, max(80, self.font_scale + amount))
        self.apply_font_scale()
        if hasattr(self, "font_scale_label"):
            self.font_scale_label.configure(text=f"Text size: {self.font_scale}%")
        self.save_study_data()

    def toggle_flashcard_saved(self):
        item = self.flashcards[self.flashcard_index]
        self.toggle_saved_item(item)
        self.flashcard_save_button.configure(
            text="Remove saved"
            if word_key(item) in self.saved_words
            else "Save word"
        )

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
            font=self.app_font(11),
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
            font=self.app_font(11, "bold"),
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
            font=self.app_font(15, "bold"),
            justify=tk.LEFT,
            wraplength=176,
        ).pack(anchor=tk.W, padx=22, pady=(28, 30))

        navigation = [
            ("Home", self.show_home),
            ("Search Dictionary", self.show_search),
            ("Browse Flashcards", self.show_flashcards),
            ("Browse Categories", self.show_categories),
            ("Interactive Quiz", self.show_quiz),
            ("Dictionary Insights", self.show_insights),
            ("Saved Words & Lists", self.show_saved_words),
            ("Study Progress", self.show_stats),
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
                font=self.app_font(12),
            ).pack(fill=tk.X, padx=10, pady=3)

        tk.Label(
            sidebar,
            text=f"{len(self.vocab)} dictionary terms",
            bg=BLACK,
            fg=MUTED_TEXT,
            font=self.app_font(10),
        ).pack(side=tk.BOTTOM, anchor=tk.W, padx=22, pady=20)

        font_controls = tk.Frame(sidebar, bg=BLACK)
        font_controls.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(8, 4))
        self.font_scale_label = tk.Label(
            font_controls,
            text=f"Text size: {self.font_scale}%",
            bg=BLACK,
            fg=MUTED_TEXT,
            font=self.app_font(10),
        )
        self.font_scale_label.pack(anchor=tk.W, padx=10, pady=(0, 5))
        tk.Button(
            font_controls,
            text="A−",
            command=lambda: self.adjust_font_scale(-10),
            padx=12,
        ).pack(side=tk.LEFT, padx=(4, 6))
        tk.Button(
            font_controls,
            text="A+",
            command=lambda: self.adjust_font_scale(10),
            padx=12,
        ).pack(side=tk.LEFT)

        self.content = tk.Frame(shell, bg=BLACK)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(
            self.root,
            text=DISCLAIMER,
            bg=BLACK_SOFT,
            fg=MUTED_TEXT,
            font=self.app_font(9),
            wraplength=950,
            justify=tk.CENTER,
            padx=12,
            pady=8,
        ).pack(fill=tk.X, side=tk.BOTTOM)

    def clear_content(self):
        for child in self.content.winfo_children():
            child.destroy()

    def speak_noongar(self, word):
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
            font=self.app_font(25, "bold"),
        ).pack(anchor=tk.W, padx=30, pady=(28, 4))
        if subtitle:
            tk.Label(
                self.content,
                text=subtitle,
                bg=BLACK,
                fg=MUTED_TEXT,
                font=self.app_font(12),
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
            ("Dictionary Insights", self.show_insights),
            ("Saved Words & Lists", self.show_saved_words),
            ("Practice Missed Words", self.practice_missed_words),
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
                font=self.app_font(16, "bold"),
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
        for row in range(4):
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
        save_button = tk.Button(
            self.content,
            text="Save selected word",
            command=lambda: self.toggle_saved_item(
                self.find_search_item(table)
            ),
            state=tk.DISABLED,
            padx=12,
            pady=6,
        )
        save_button.pack(anchor=tk.W, padx=30, pady=(0, 8))
        table = self.make_results_table(self.content)

        def update_speak_button(event):
            selection = event.widget.selection()
            speak_button.configure(
                state=tk.NORMAL if selection else tk.DISABLED
            )
            save_button.configure(
                state=tk.NORMAL if selection else tk.DISABLED
            )

        table.bind("<<TreeviewSelect>>", update_speak_button)

        def update_results(*_):
            value = query.get().strip().casefold()
            table.delete(*table.get_children())
            speak_button.configure(state=tk.DISABLED)
            if not value:
                return
            matches = search_vocabulary(self.vocab, value)
            for item in matches:
                table.insert(
                    "",
                    tk.END,
                    values=(item["noongar"], item["english"], item["category"]),
                )

        query.trace_add("write", update_results)
        search_entry.focus_set()

    def find_search_item(self, table):
        selected = table.selection()
        if not selected:
            return None
        values = table.item(selected[0], "values")
        return next(
            (
                item
                for item in self.vocab
                if (item["noongar"], item["english"], item["category"])
                == tuple(values)
            ),
            None,
        )

    def toggle_saved_item(self, item):
        if item is None:
            return
        key = word_key(item)
        if key in self.saved_words:
            self.saved_words.remove(key)
            for words in self.word_lists.values():
                words.discard(key)
        else:
            self.saved_words.add(key)
        self.save_study_data()

    def speak_selected_search_result(self, table):
        selected = table.selection()
        if selected:
            values = table.item(selected[0], "values")
            if values:
                self.speak_noongar(str(values[0]))

    def show_insights(self):
        summaries = summarize_categories(self.vocab)
        self.page_heading(
            "Dictionary Insights",
            "A count of dictionary entries by category. These are vocabulary records, not measures of how often words are used.",
        )
        if not summaries:
            tk.Label(
                self.content,
                text="No vocabulary entries are available to analyse.",
                bg=BLACK,
                fg=MUTED_TEXT,
                font=self.app_font(12),
            ).pack(anchor=tk.W, padx=30, pady=12)
            return

        largest = summaries[0]
        tk.Label(
            self.content,
            text=(
                f"{len(self.vocab)} dictionary entries across "
                f"{len(summaries)} categories. Largest category: "
                f"{largest.category} ({largest.count} entries, "
                f"{largest.percentage:.1f}%)."
            ),
            bg=BLACK_SOFT,
            fg=TEXT,
            font=self.app_font(13, "bold"),
            wraplength=730,
            justify=tk.LEFT,
            padx=16,
            pady=12,
        ).pack(fill=tk.X, padx=30, pady=(0, 16))

        chart = tk.Frame(self.content, bg=BLACK)
        chart.pack(fill=tk.BOTH, expand=True, padx=30, pady=(0, 20))
        maximum = max(summary.count for summary in summaries)
        for summary in summaries:
            row = tk.Frame(chart, bg=BLACK)
            row.pack(fill=tk.X, pady=4)
            tk.Label(
                row,
                text=summary.category,
                bg=BLACK,
                fg=TEXT,
                font=self.app_font(11),
                anchor=tk.W,
                width=26,
            ).pack(side=tk.LEFT)
            bar = tk.Canvas(
                row,
                height=20,
                bg=BLACK_SOFT,
                highlightthickness=0,
                borderwidth=0,
            )
            bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(4, 10))

            def draw_bar(event, canvas=bar, count=summary.count):
                canvas.delete("all")
                width = max(0, int(event.width * count / maximum))
                if width:
                    canvas.create_rectangle(
                        0,
                        2,
                        width,
                        event.height - 2,
                        fill=YELLOW,
                        outline="",
                    )

            bar.bind("<Configure>", draw_bar)
            tk.Label(
                row,
                text=f"{summary.count} · {summary.percentage:.1f}%",
                bg=BLACK,
                fg=MUTED_TEXT,
                font=self.app_font(10),
                anchor=tk.E,
                width=12,
            ).pack(side=tk.LEFT)

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
        tk.Button(
            sort_controls,
            text="Save selected word",
            command=lambda: self.save_selected_category_word(
                results, selected.get()
            ),
            padx=10,
            pady=5,
        ).pack(side=tk.LEFT, padx=(12, 0))
        results_frame = tk.Frame(self.content, bg=BLACK)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=(8, 25))
        results = tk.Text(
            results_frame,
            bg=BLACK_SOFT,
            fg=TEXT,
            insertbackground=YELLOW,
            font=self.app_font(12),
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=16,
            pady=12,
            spacing1=5,
            spacing3=14,
            state=tk.DISABLED,
        )
        results.tag_configure("primary", font=self.app_font(12, "bold"))
        results.tag_configure("secondary", font=self.app_font(12))
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

    def save_selected_category_word(self, results, category):
        try:
            selected = results.get(tk.SEL_FIRST, tk.SEL_LAST).strip()
        except tk.TclError:
            messagebox.showinfo(
                "Select a word",
                "Highlight one Noongar or English word before saving it.",
                parent=self.root,
            )
            return
        item = next(
            (
                candidate
                for candidate in self.vocab
                if candidate["category"] == category
                if selected in (candidate["noongar"], candidate["english"])
            ),
            None,
        )
        if item is None:
            messagebox.showinfo(
                "Select one word",
                "Highlight exactly one Noongar or English word.",
                parent=self.root,
            )
            return
        self.toggle_saved_item(item)

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
            font=self.app_font(12),
        ).pack(pady=(30, 15))
        tk.Label(
            card,
            textvariable=self.flashcard_word,
            bg=BLACK_SOFT,
            fg=TEXT,
            font=self.app_font(32, "bold"),
            wraplength=650,
        ).pack(pady=35)
        tk.Label(
            card,
            textvariable=self.flashcard_answer,
            bg=BLACK_SOFT,
            fg=TEXT,
            font=self.app_font(20),
        ).pack(pady=10)
        tk.Label(
            card,
            textvariable=self.flashcard_feedback,
            bg=BLACK_SOFT,
            fg=MUTED_TEXT,
            font=self.app_font(11),
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
        self.flashcard_save_button = tk.Button(
            controls,
            text="Save word",
            command=self.toggle_flashcard_saved,
            padx=15,
            pady=8,
        )
        self.flashcard_save_button.pack(side=tk.LEFT, padx=8)
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
        self.flashcard_save_button.configure(
            text="Remove saved"
            if word_key(card) in self.saved_words
            else "Save word"
        )
        self.flashcard_answer.set("")
        self.flashcard_feedback.set("")
        self.flashcard_revealed = False

    def reveal_flashcard(self):
        if not self.flashcard_revealed:
            card = self.flashcards[self.flashcard_index]
            self.flashcard_answer.set(card["english"])
            self.flashcard_feedback.set(card["category"])
            self.flashcard_revealed = True
            key = word_key(card)
            self.reviewed_words.add(key)
            self.save_study_data()

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
            values=[ALL_CATEGORIES, "Practice missed words", *self.categories],
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
        if self.quiz_category.get() == "Practice missed words":
            pool = [
                item for item in self.vocab if word_key(item) in self.missed_words
            ]
            if not pool:
                messagebox.showinfo(
                    "No missed words",
                    "Complete a quiz and answer some questions incorrectly first.",
                    parent=self.root,
                )
                return
        elif self.quiz_category.get() == ALL_CATEGORIES:
            pool = self.vocab
        else:
            pool = [
                item
                for item in self.vocab
                if item["category"] == self.quiz_category.get()
            ]
        answer_pool = (
            self.vocab
            if self.quiz_category.get() == "Practice missed words"
            else pool
        )
        if len({item["english"].casefold() for item in answer_pool}) < 2:
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

    def practice_missed_words(self):
        self.show_quiz()
        self.quiz_category.set("Practice missed words")
        self.start_quiz()

    def show_quiz_question(self):
        for child in self.quiz_area.winfo_children():
            child.destroy()
        if self.quiz_index >= len(self.quiz_questions):
            self.show_quiz_result()
            return

        question = self.quiz_questions[self.quiz_index]
        option_pool = self.quiz_pool
        if self.quiz_category.get() == "Practice missed words":
            option_pool = self.vocab
        elif self.quiz_category.get() != ALL_CATEGORIES:
            option_pool = [
                item
                for item in option_pool
                if item["category"] == self.quiz_category.get()
            ]
        options = build_quiz_options(question, option_pool)
        self.quiz_answer = tk.StringVar(value="")

        tk.Label(
            self.quiz_area,
            text=f"Question {self.quiz_index + 1} of {len(self.quiz_questions)}",
            bg=BLACK,
            fg=MUTED_TEXT,
            font=self.app_font(12),
        ).pack(anchor=tk.W, pady=(8, 14))
        tk.Label(
            self.quiz_area,
            text=f"What is the English meaning of '{question['noongar']}'?",
            bg=BLACK,
            fg=TEXT,
            font=self.app_font(20, "bold"),
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
            font=self.app_font(11),
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
                font=self.app_font(13),
                anchor=tk.W,
            ).pack(anchor=tk.W, pady=4)
        self.quiz_feedback = tk.StringVar()
        tk.Label(
            self.quiz_area,
            textvariable=self.quiz_feedback,
            bg=BLACK,
            font=self.app_font(12, "bold"),
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
        key = word_key(question)
        answer_was_correct = (
            selected.casefold() == question["english"].casefold()
        )
        self.daily_accuracy = record_daily_accuracy(
            self.daily_accuracy,
            int(answer_was_correct),
            1,
        )
        if answer_was_correct:
            self.correct_answers += 1
            self.quiz_correct += 1
            self.missed_words.discard(key)
            self.quiz_feedback.set("Correct! Well done.")
        else:
            self.missed_words.add(key)
            self.quiz_feedback.set(
                f"Not quite. The answer is: {question['english']}"
            )
        self.save_study_data()
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
            font=self.app_font(22, "bold"),
        ).pack(anchor=tk.W, pady=12)
        tk.Label(
            self.quiz_area,
            text=f"You answered {self.quiz_correct} of "
            f"{len(self.quiz_questions)} questions correctly.",
            bg=BLACK,
            font=self.app_font(14),
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
            "Study Progress",
            "Quiz totals, daily accuracy, reviewed words, and missed-word practice are saved on this device.",
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
            ("Words reviewed", str(len(self.reviewed_words))),
            ("Words to practise", str(len(self.missed_words))),
            ("Saved words", str(len(self.saved_words))),
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
                font=self.app_font(13),
            ).pack(side=tk.LEFT)
            tk.Label(
                row,
                text=value,
                bg=BLACK_SOFT,
                fg=TEXT,
                font=self.app_font(14, "bold"),
            ).pack(side=tk.RIGHT)

        self.draw_daily_accuracy_chart()

        tk.Button(
            self.content,
            text="Clear learning progress",
            command=self.clear_learning_progress,
            padx=12,
            pady=7,
        ).pack(anchor=tk.W, padx=30, pady=12)

    def draw_daily_accuracy_chart(self):
        section = tk.Frame(self.content, bg=BLACK)
        section.pack(fill=tk.X, padx=30, pady=(16, 8))
        tk.Label(
            section,
            text="Quiz accuracy by date",
            bg=BLACK,
            fg=TEXT,
            font=self.app_font(16, "bold"),
        ).pack(anchor=tk.W, pady=(0, 4))
        history = sorted(self.daily_accuracy.items())
        if not history:
            tk.Label(
                section,
                text="Complete quiz questions to start tracking daily accuracy.",
                bg=BLACK,
                fg=MUTED_TEXT,
                font=self.app_font(11),
            ).pack(anchor=tk.W, pady=(4, 12))
            return

        tk.Label(
            section,
            text="Each point shows the percentage correct on a day you answered quiz questions.",
            bg=BLACK,
            fg=MUTED_TEXT,
            font=self.app_font(11),
            wraplength=700,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 8))
        plot_width = max(640, 90 * len(history) + 90)
        chart = tk.Canvas(
            section,
            height=290,
            width=plot_width,
            bg=BLACK,
            highlightthickness=0,
            scrollregion=(0, 0, plot_width, 290),
        )
        chart.pack(fill=tk.X, expand=True)
        scrollbar = ttk.Scrollbar(
            section,
            orient=tk.HORIZONTAL,
            command=chart.xview,
        )
        chart.configure(xscrollcommand=scrollbar.set)
        if plot_width > 700:
            scrollbar.pack(fill=tk.X, pady=(2, 12))

        left, right, top, bottom = 52, plot_width - 24, 24, 226
        for percentage in (0, 25, 50, 75, 100):
            y = bottom - (bottom - top) * percentage / 100
            chart.create_line(left, y, right, y, fill=LINE)
            chart.create_text(
                left - 10,
                y,
                text=f"{percentage}%",
                fill=MUTED_TEXT,
                anchor=tk.E,
                font=self.app_font(9),
            )

        points = []
        for index, (day, counts) in enumerate(history):
            x = (
                left + (right - left) / 2
                if len(history) == 1
                else left + (right - left) * index / (len(history) - 1)
            )
            accuracy = counts["correct"] / counts["attempted"] * 100
            y = bottom - (bottom - top) * accuracy / 100
            points.append((x, y))
            chart.create_text(
                x,
                bottom + 22,
                text=f"{day[5:7]}/{day[8:10]}",
                fill=MUTED_TEXT,
                font=self.app_font(9),
            )
            chart.create_text(
                x,
                y - 12,
                text=f"{accuracy:.0f}%",
                fill=YELLOW,
                font=self.app_font(9, "bold"),
            )
        if len(points) > 1:
            chart.create_line(
                *[coordinate for point in points for coordinate in point],
                fill=YELLOW,
                width=2,
            )
        for x, y in points:
            chart.create_oval(
                x - 4,
                y - 4,
                x + 4,
                y + 4,
                fill=YELLOW,
                outline=BLACK,
            )

    def clear_learning_progress(self):
        if not messagebox.askyesno(
            "Clear learning progress",
            "Clear quiz totals, daily accuracy history, reviewed words, and missed-word practice? "
            "Saved words and lists will be kept.",
            parent=self.root,
        ):
            return
        self.total_quiz_questions = 0
        self.correct_answers = 0
        self.daily_accuracy.clear()
        self.reviewed_words.clear()
        self.missed_words.clear()
        self.save_study_data()
        self.show_stats()

    def show_saved_words(self):
        self.page_heading(
            "Saved Words & Lists",
            "Bookmark words from Search, Categories, or Flashcards, then organise them into personal lists.",
        )
        controls = tk.Frame(self.content, bg=BLACK)
        controls.pack(fill=tk.X, padx=30, pady=(0, 12))
        list_name = tk.StringVar()
        ttk.Entry(controls, textvariable=list_name, width=30).pack(
            side=tk.LEFT, padx=(0, 8)
        )
        selected_list = tk.StringVar(value="All saved words")
        list_selector = ttk.Combobox(
            controls,
            textvariable=selected_list,
            values=["All saved words", *sorted(self.word_lists, key=str.casefold)],
            state="readonly",
            width=28,
        )
        list_selector.pack(side=tk.LEFT, padx=8)
        delete_list_button = ttk.Button(
            controls,
            text="Delete selected list",
            command=lambda: self.delete_word_list(
                selected_list, list_selector, refresh_list, delete_list_button
            ),
            state=tk.DISABLED,
        )
        delete_list_button.pack(side=tk.LEFT, padx=8)
        rows = tk.Frame(self.content, bg=BLACK)
        rows.pack(fill=tk.BOTH, expand=True, padx=30, pady=8)

        def refresh_list():
            for child in rows.winfo_children():
                child.destroy()
            list_name_value = selected_list.get()
            if list_name_value == "All saved words":
                keys = self.saved_words
            else:
                keys = self.word_lists.get(list_name_value, set())
            items = [item for item in self.vocab if word_key(item) in keys]
            if not items:
                tk.Label(
                    rows,
                    text=(
                        "No saved words yet. Use Save beside a word while browsing."
                        if list_name_value == "All saved words"
                        else "This list is empty. Add a saved word using its list selector."
                    ),
                    bg=BLACK,
                    fg=MUTED_TEXT,
                    font=self.app_font(12),
                    wraplength=650,
                ).pack(anchor=tk.W, pady=12)
                return
            for item in items:
                row = tk.Frame(
                    rows,
                    bg=BLACK_SOFT,
                    highlightbackground=LINE,
                    highlightthickness=1,
                    padx=12,
                    pady=8,
                )
                row.pack(fill=tk.X, pady=4)
                description = tk.Frame(row, bg=BLACK_SOFT)
                description.pack(side=tk.LEFT, fill=tk.X, expand=True)
                tk.Label(
                    description,
                    text=item["noongar"],
                    bg=BLACK_SOFT,
                    fg=TEXT,
                    font=self.app_font(13, "bold"),
                ).pack(anchor=tk.W)
                tk.Label(
                    description,
                    text=f'{item["english"]} · {item["category"]}',
                    bg=BLACK_SOFT,
                    fg=MUTED_TEXT,
                    font=self.app_font(11),
                ).pack(anchor=tk.W)
                if list_name_value == "All saved words" and self.word_lists:
                    destination = ttk.Combobox(
                        row,
                        values=sorted(self.word_lists, key=str.casefold),
                        state="readonly",
                        width=18,
                    )
                    destination.pack(side=tk.LEFT, padx=5)
                    destination.current(0)

                    def add_to_list(word=item, selection=destination):
                        target = selection.get()
                        if target:
                            self.word_lists[target].add(word_key(word))
                            self.save_study_data()
                            refresh_list()

                    tk.Button(
                        row, text="Add to list", command=add_to_list, padx=8
                    ).pack(side=tk.LEFT, padx=4)
                elif list_name_value != "All saved words":
                    tk.Button(
                        row,
                        text="Remove from list",
                        command=lambda word=item, name=list_name_value: self.remove_from_list(
                            word, name, refresh_list
                        ),
                        padx=8,
                    ).pack(side=tk.LEFT, padx=4)
                tk.Button(
                    row,
                    text="Mark reviewed",
                    command=lambda word=item: self.mark_word_reviewed(word),
                    padx=8,
                ).pack(side=tk.LEFT, padx=4)
                tk.Button(
                    row,
                    text="Remove saved",
                    command=lambda word=item: self.remove_saved_word(
                        word, refresh_list
                    ),
                    padx=8,
                ).pack(side=tk.LEFT, padx=4)
                tk.Button(
                    row,
                    text="Speak",
                    command=lambda word=item["noongar"]: self.speak_noongar(word),
                    padx=8,
                ).pack(side=tk.LEFT, padx=4)

        def create_list():
            name = list_name.get().strip()
            if not name:
                messagebox.showinfo(
                    "Enter a list name",
                    "Type a name for your study list.",
                    parent=self.root,
                )
                return
            if any(existing.casefold() == name.casefold() for existing in self.word_lists):
                messagebox.showerror(
                    "List already exists",
                    "Choose a different name for this list.",
                    parent=self.root,
                )
                return
            self.word_lists[name] = set()
            list_name.set("")
            list_selector.configure(
                values=["All saved words", *sorted(self.word_lists, key=str.casefold)]
            )
            selected_list.set(name)
            self.save_study_data()
            delete_list_button.configure(state=tk.NORMAL)
            refresh_list()

        ttk.Button(controls, text="Create list", command=create_list).pack(
            side=tk.LEFT
        )
        def select_list(event):
            selected_list.set(event.widget.get())
            delete_list_button.configure(
                state=tk.NORMAL
                if selected_list.get() != "All saved words"
                else tk.DISABLED
            )
            refresh_list()

        list_selector.bind("<<ComboboxSelected>>", select_list)
        refresh_list()

    def remove_from_list(self, item, name, refresh):
        self.word_lists.get(name, set()).discard(word_key(item))
        self.save_study_data()
        refresh()

    def remove_saved_word(self, item, refresh):
        key = word_key(item)
        self.saved_words.discard(key)
        for words in self.word_lists.values():
            words.discard(key)
        self.save_study_data()
        refresh()

    def mark_word_reviewed(self, item):
        self.reviewed_words.add(word_key(item))
        self.save_study_data()

    def delete_word_list(
        self, selected_list, list_selector, refresh, delete_list_button
    ):
        name = selected_list.get()
        if name == "All saved words" or not messagebox.askyesno(
            "Delete list",
            f"Delete “{name}”? Its saved words will remain bookmarked.",
            parent=self.root,
        ):
            return
        self.word_lists.pop(name, None)
        selected_list.set("All saved words")
        delete_list_button.configure(state=tk.DISABLED)
        list_selector.configure(
            values=["All saved words", *sorted(self.word_lists, key=str.casefold)]
        )
        self.save_study_data()
        refresh()


if __name__ == "__main__":
    root = tk.Tk()
    app = NoongarApp(root)
    if root.winfo_exists():
        root.mainloop()
