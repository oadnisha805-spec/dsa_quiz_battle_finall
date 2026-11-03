"""gui.py: the screens of DSA Quiz Battle (the Frontend).

This file only draws screens and reacts to clicks and keys. All quiz logic (which question is
next, is the answer right, the scores) lives in the game object it is given (see game.py):

    players             -> list of the player names
    current_question()  -> dict: text, options (4), correct (0-3), number, total (+ category)
    current_player()    -> name of the player whose turn it is
    submit_answer(i)    -> True/False   (i is 0-3, or None if time ran out)
    next_question()     -> False when there are no more questions
    scores              -> dict, player name -> score
    get_results()       -> dict: scores, correct, wrong, winner (None on a tie), is_tie
    review_all()        -> (optional) answered questions, newest first (this is the stack)

The drawing tools (gradient buttons, glow cards, animations, sound) are in ui_kit.py.
"""
import math
import random
import time
import tkinter as tk

import ui_kit
from ui_kit import (ACCENT, BACKDROP_MID, BG, BLUE, CARD_FILL, CanvasButton, DARK_TEXT, DIM, Effects, GOLD, GREEN,
                    IconButton, MUTED, ORANGE, PINK, RED, Sound, TEXT, TimerRing, VIOLET, chip, clear_cache,
                    draw_backdrop, draw_rich_text, font, glow_card, init_fonts, mix, photo, pill_png, round_rect,
                    shorten, star_points)

QUESTION_TIME = 15      # seconds per question; set to 0 to turn the timer off
FIELD = "#0f0830"       # background of the name boxes

CORRECT_WORDS = ["Wow!", "Amazing!", "Bravo!", "Brilliant!", "Excellent!", "Fantastic!", "Superb!",
                 "Awesome!", "Great job!", "Well done!", "Perfect!", "Genius!"]
WRONG_WORDS = ["Not quite!", "So close!", "Almost!", "Oops!"]
STREAK_WORDS = {2: "Double!", 3: "Hat-trick!"}


def cheer_for(streak, speed, last):
    """Pick the encouraging word shown after a correct answer. Returns (word, colour)."""
    if streak >= 4:
        return "Unstoppable!", ORANGE
    if streak in STREAK_WORDS:
        return STREAK_WORDS[streak], ORANGE
    if speed >= 0.7 and last != "Lightning fast!":
        return "Lightning fast!", "#5ee6ff"
    return random.choice([word for word in CORRECT_WORDS if word != last]), GOLD


class Lay:
    """Scales the 1000 x 720 design to the real window size (and centres it)."""

    def __init__(self, width, height):
        self.w, self.h = width, height
        self.s = max(0.55, min(width / 1000.0, height / 720.0))

    def x(self, value):
        return self.w / 2 + (value - 500) * self.s

    def y(self, value):
        return self.h / 2 + (value - 360) * self.s

    def n(self, value):
        return value * self.s


# ------------------------------------------------------------------------ the window
class App(tk.Tk):
    """The window. `game_factory(players)` must return a fresh game object.
    `on_finish(results)` (optional) is called once when a game ends, e.g. to save to the database.
    """

    def __init__(self, game_factory, on_finish=None):
        super().__init__()
        init_fonts(self)
        self.title("DSA Quiz Battle")
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        width, height = min(1040, int(screen_w * 0.92)), min(760, int(screen_h * 0.86))
        self.start_size = (width, height)
        self.geometry(f"{width}x{height}+{max(0, (screen_w - width) // 2)}+{max(0, (screen_h - height) // 3)}")
        self.minsize(720, 540)
        self.game_factory = game_factory
        self.on_finish = on_finish
        self.game = None
        self.players = []
        self.results = None
        self.current = None
        self.fullscreen = False
        self.resize_job = None
        self.last_size = None

        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.effects = Effects(self.canvas)
        self.sound = Sound()
        self.sound_button = IconButton(self.canvas, "sound_on", self.toggle_sound)
        self.screens = {}
        for screen in (WelcomeScreen, InstructionsScreen, PlayerNamesScreen, QuizScreen, ResultsScreen):
            self.screens[screen.__name__] = screen(self)
        self.bind("<Key>", self._on_key)
        self.canvas.bind("<Configure>", self._on_resize)
        self.show("WelcomeScreen")

    # ---- layout and drawing
    def layout(self):
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        if width < 100 or height < 100:
            width, height = self.start_size
        return Lay(width, height)

    def redraw(self):
        lay = self.layout()
        self.canvas.delete("ui")
        self.draw_global(lay)
        if self.current is not None:
            self.current.draw(lay)
        self.canvas.tag_raise("fx")

    def relayout(self):
        lay = self.layout()
        self.canvas.delete("decor")
        draw_backdrop(self.canvas, lay.w, lay.h)
        self.redraw()

    def _on_resize(self, event):
        if self.resize_job is not None:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(120, self._finish_resize)

    def _finish_resize(self):
        self.resize_job = None
        size = (self.canvas.winfo_width(), self.canvas.winfo_height())
        if size != self.last_size:
            self.last_size = size
            self.relayout()

    def draw_global(self, lay):
        self.sound_button.kind = "sound_on" if self.sound.enabled else "sound_off"
        self.sound_button.size = int(lay.n(44))
        self.sound_button.draw(lay.x(955), lay.y(36))

    def toggle_sound(self):
        self.sound.toggle()
        self.sound_button.set_kind("sound_on" if self.sound.enabled else "sound_off")

    # ---- screens
    def show(self, name):
        if self.current is not None:
            self.current.on_hide()
        self.effects.cancel()
        self.current = self.screens[name]
        self.focus_set()    # take the keyboard focus away from hidden text boxes
        self.current.on_show()
        self.relayout()

    def start_game(self, players):
        self.players = players
        self.game = self.game_factory(players)
        self.show("QuizScreen")

    def play_again(self):
        self.start_game(self.players)

    def finish_game(self):
        self.results = self.game.get_results()
        if self.on_finish:
            self.on_finish(self.results)
        self.show("ResultsScreen")

    # ---- keyboard
    def _on_key(self, event):
        if event.keysym == "F11" or (event.keysym == "Escape" and self.fullscreen):
            self.fullscreen = not self.fullscreen
            self.attributes("-fullscreen", self.fullscreen)
            return
        if isinstance(self.focus_get(), tk.Entry):
            return      # the player is typing a name
        if event.char and event.char.lower() == "m":
            self.toggle_sound()
            return
        if self.current is not None:
            self.current.on_key(event)

    def destroy(self):
        if self.current is not None:
            self.current.on_hide()
        self.effects.cancel()
        super().destroy()


class Screen:
    """Base class: every screen draws itself on the shared canvas."""

    def __init__(self, app):
        self.app = app
        self.canvas = app.canvas

    def button(self, lay, cx, cy, text, command, style="primary", width=320, height=56, size=19, **options):
        button = CanvasButton(self.canvas, text, command, style, width=int(lay.n(width)), height=int(lay.n(height)),
                              size=lay.n(size), **options)
        button.draw(cx, cy)
        return button

    def draw(self, lay):
        pass

    def on_show(self):
        pass

    def on_hide(self):
        pass

    def on_key(self, event):
        pass


# ------------------------------------------------------------------------- Welcome
class WelcomeScreen(Screen):
    def draw(self, lay):
        c, X, Y, n = self.canvas, lay.x, lay.y, lay.n
        c.create_text(X(500), Y(70), text="READY FOR THE", font=font(n(20), True), fill=MUTED, tags="ui")
        draw_rich_text(c, X(500), Y(150), "DSA Quiz Battle", n(900), sizes=tuple(int(n(v)) for v in (84, 72, 60, 48)),
                       accent_words=2, max_lines=1)
        c.create_text(X(500), Y(232), text="Challenge a friend and master Data Structures and Algorithms",
                      font=font(n(20), False), fill=MUTED, tags="ui")
        glow_card(c, X(190), Y(282), X(810), Y(556), ("ui",), radius=n(34))
        self.start_button = self.button(lay, X(500), Y(344), "Start Game", lambda: self.app.show("PlayerNamesScreen"),
                                        width=520, height=64, size=24)
        self.instructions_button = self.button(lay, X(500), Y(422), "Instructions",
                                               lambda: self.app.show("InstructionsScreen"), width=520, height=64, size=22)
        self.exit_button = self.button(lay, X(500), Y(500), "Exit", self.app.destroy, style="ghost", width=520,
                                       height=64, size=22)
        labels = (f"{QUESTION_TIME} sec timer" if QUESTION_TIME else "No timer", "50:50 lifeline", "Streak cheers", "1-2 players")
        gap, pad, size = n(12), int(n(14)), int(n(14))
        widths = [ui_kit.text_width(t, size) + 2 * pad for t in labels]
        x = X(500) - (sum(widths) + gap * (len(labels) - 1)) / 2
        for text in labels:
            x = chip(c, x, Y(612), text, "#2a1a7a", "#cdbfff", "ui", size=size, pad=pad, height=int(n(30))) + gap
        c.create_text(X(500), Y(680), text="Nisha   ·   Vanshika   ·   Kajal   ·   Ravina", font=font(n(15), False),
                      fill=DIM, tags="ui")


# --------------------------------------------------------------------- Instructions
class InstructionsScreen(Screen):
    RULES = [
        "Play alone, or with a friend: then you take turns, one question each.",
        "Choose one of the four answers, or press the keys 1 to 4.",
        "A correct answer earns points. A wrong answer earns zero.",
        "Beat the countdown! If time runs out, you get zero for that question.",
        "Use your 50:50 lifeline once per game to remove two wrong answers.",
        "Answer correctly in a row to build a streak and win bigger cheers.",
        "The player with the highest score wins. Equal scores are a tie.",
    ]

    def draw(self, lay):
        c, X, Y, n = self.canvas, lay.x, lay.y, lay.n
        draw_rich_text(c, X(500), Y(60), "How to play", n(900), sizes=(int(n(46)),), accent_words=1, max_lines=1)
        glow_card(c, X(110), Y(104), X(890), Y(624), ("ui",), radius=n(32))
        self.rule_buttons = []
        for i, rule in enumerate(self.RULES):
            self.rule_buttons.append(self.button(lay, X(500), Y(144 + i * 71.5), rule, None, width=720, height=56,
                                                 size=17, badge=str(i + 1), align="left", bold=True))
        self.back_button = self.button(lay, X(500), Y(670), "Back", lambda: self.app.show("WelcomeScreen"),
                                       style="gold", width=240, height=52, size=20)


# ------------------------------------------------------------------- Player names
class PlayerNamesScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.error = ""
        self.lay = None
        self.count = 2                       # 1 = play alone, 2 = play with a friend
        self.vars = [tk.StringVar(), tk.StringVar()]
        limit = (app.register(lambda text: len(text) <= 16), "%P")
        self.entries = []
        for var in self.vars:
            entry = tk.Entry(app.canvas, textvariable=var, font=font(22, False), bg=FIELD, fg=TEXT,
                             insertbackground=TEXT, relief="flat", highlightthickness=0,
                             validate="key", validatecommand=limit)
            entry.bind("<Return>", self.on_enter)
            self.entries.append(entry)

    def on_show(self):
        self.error = ""
        self.app.after_idle(self.entries[0].focus_set)

    def on_enter(self, event):
        """Enter in the first box moves to the second box (if it is empty), otherwise starts the game."""
        if event.widget is self.entries[0] and self.count == 2 and not self.vars[1].get().strip():
            self.entries[1].focus_set()
        else:
            self.start()

    def set_count(self, count):
        self.count = count
        self.error = ""
        self.app.redraw()
        self.app.after_idle(self.entries[0].focus_set)

    def draw(self, lay):
        self.lay = lay
        c, X, Y, n = self.canvas, lay.x, lay.y, lay.n
        draw_rich_text(c, X(500), Y(80), "Who is playing?", n(900), sizes=(int(n(46)),), accent_words=1, max_lines=1)
        c.create_text(X(500), Y(128), text="Play alone or challenge a friend", font=font(n(19), False), fill=MUTED,
                      tags="ui")
        for k, label in ((1, "1 Player"), (2, "2 Players")):
            button = self.button(lay, X(410 + (k - 1) * 180), Y(190), label, lambda k=k: self.set_count(k),
                                 style="primary" if self.count == k else "ghost", width=170, height=46, size=18)
        card_bottom = 382 + (self.count - 1) * 128
        glow_card(c, X(150), Y(236), X(850), Y(card_bottom), ("ui",), radius=n(32))
        for i, color in enumerate((VIOLET, PINK)[:self.count]):
            top = 280 + i * 128
            c.create_text(X(206), Y(top - 14), text=f"Player {i + 1}" if self.count == 2 else "Your name", anchor="w",
                          font=font(n(16), True), fill=MUTED, tags="ui")
            round_rect(c, X(200), Y(top), X(800), Y(top + 66), n(33), fill=FIELD, outline=color, width=2, tags="ui")
            c.create_oval(X(212), Y(top + 11), X(256), Y(top + 55), fill=color, outline="", tags="ui")
            c.create_text(X(234), Y(top + 33), text=str(i + 1), font=font(n(22), True), fill="#ffffff", tags="ui")
            c.create_window(X(278), Y(top + 33), window=self.entries[i], anchor="w", width=int(n(490)),
                            height=int(n(40)), tags="ui")
        self.error_y = card_bottom + 26
        self.draw_error()
        self.start_button = self.button(lay, X(500), Y(card_bottom + 76), "Start Battle" if self.count == 2 else "Start Game",
                                        self.start, width=360, height=62, size=23)
        self.back_button = self.button(lay, X(500), Y(card_bottom + 150), "Back", lambda: self.app.show("WelcomeScreen"),
                                       style="ghost", width=240, height=50, size=19)

    def draw_error(self):
        self.canvas.delete("err")
        if self.lay is not None:
            self.canvas.create_text(self.lay.x(500), self.lay.y(self.error_y), text=self.error,
                                    font=font(self.lay.n(18), True), fill=RED, tags=("ui", "err"))

    def set_error(self, message):
        self.error = message
        self.draw_error()

    def start(self):
        names = [var.get().strip() for var in self.vars[:self.count]]
        if not all(names):
            self.set_error("Please enter your name." if self.count == 1 else "Please enter a name for both players.")
        elif self.count == 2 and names[0].lower() == names[1].lower():
            self.set_error("The two players need different names.")
        else:
            self.app.start_game(names)


# ------------------------------------------------------------------------- Quiz
class QuizScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.lay = None
        self.timer_job = None
        self.deadline = 0.0
        self.held = False
        self.held_left = 0.0
        self.mode = "play"           # "countdown", "play", "pause" or "review"
        self.countdown_jobs = []
        self.review_list = []
        self.review_index = 0
        self.q = None
        self.names = []
        self.scores, self.streak, self.best, self.lifeline, self.flash = {}, {}, {}, {}, {}
        self.last_word = None
        self.turn_player = ""
        self.remaining = float(QUESTION_TIME)
        self.last_tick = None
        self.ring = TimerRing(app.canvas)
        self.reset_stage()
        self.option_buttons = []
        self.next_button = self.fifty_button = self.review_button = self.pause_button = None
        self.reset_question_state()

    def reset_stage(self):
        """State of the two seated players and the sliding "turn" pill."""
        self.act = [0.6, 0.6]            # how "awake" each station looks (0 waiting ... 1 active)
        self.act_from, self.act_to = [0.6, 0.6], [0.6, 0.6]
        self.turn_t0 = None
        self.turn_idx = None
        self.pill_x, self.pill_from, self.pill_to, self.pill_prog = None, 500.0, 500.0, 1.0
        self.mood, self.bubble, self.bounce_until = {}, {}, {}
        self.anim_job = None

    def reset_question_state(self):
        self.answered = False
        self.picked = self.right = None
        self.option_state = ["normal"] * 4
        self.hidden = set()
        self.feedback = None

    @property
    def game(self):
        return self.app.game

    # ---- start of a game / a question
    def on_show(self):
        self.names = list(self.game.players)[:2]
        self.scores = {name: self.game.scores.get(name, 0) for name in self.names}
        self.streak = {name: 0 for name in self.names}
        self.best = {name: 0 for name in self.names}
        self.lifeline = {name: True for name in self.names}
        self.flash = {}
        self.last_word = None
        self.stop_anim()
        self.reset_stage()
        self.mode = "countdown"
        self.render_question()
        self.start_countdown()

    def on_hide(self):
        self.stop_timer()
        self.cancel_countdown()
        self.stop_anim()

    def render_question(self):
        self.q = self.game.current_question()
        self.turn_player = self.game.current_player()
        self.reset_question_state()
        self.remaining = float(QUESTION_TIME)
        self.last_tick = None
        self.ring.set(QUESTION_TIME, QUESTION_TIME) if QUESTION_TIME > 0 else self.ring.set_off()
        self.mood = {}
        self.begin_turn()

    def start_play(self):
        self.mode = "play"
        self.start_timer()

    # ---- the 3-2-1-GO countdown
    def start_countdown(self):
        self.cancel_countdown()
        self.mode = "countdown"
        steps = [("3", 80, "count", ACCENT), ("2", 830, "count", ACCENT), ("1", 1580, "count", ACCENT),
                 ("GO!", 2330, "go", GOLD)]
        for text, delay, sound, color in steps:
            self.countdown_jobs.append(self.app.after(delay, lambda t=text, s=sound, col=color: self.countdown_step(t, s, col)))
        self.countdown_jobs.append(self.app.after(2900, self.finish_countdown))

    def countdown_step(self, text, sound, color):
        if self.app.current is not self or self.mode != "countdown":
            return
        lay = self.lay or self.app.layout()
        self.app.sound.play(sound)
        self.app.effects.banner(lay.x(500), lay.y(420), text, color, size=int(lay.n(150 if text != "GO!" else 120)),
                                hold=360)
        if text == "GO!":
            self.app.effects.burst(lay.x(500), lay.y(420), count=26, power=10)

    def finish_countdown(self):
        if self.app.current is self and self.mode == "countdown":
            self.mode = "play"
            self.begin_turn()
            self.start_play()
            self.app.redraw()

    def cancel_countdown(self):
        for job in self.countdown_jobs:
            self.app.after_cancel(job)
        self.countdown_jobs = []

    # ---- drawing
    def draw(self, lay):
        self.lay = lay
        if self.q is None:
            return
        if self.mode == "pause":
            return self.draw_pause(lay)
        if self.mode == "review":
            return self.draw_review(lay)
        c, X, Y, n = self.canvas, lay.x, lay.y, lay.n
        q = self.q

        # header: question counter, progress bar, pause button
        c.create_text(X(50), Y(30), text=f"Question {q['number']} of {q['total']}", anchor="w", font=font(n(19), True),
                      fill=MUTED, tags="ui")
        track_left, track_right = X(50), X(840)
        round_rect(c, track_left, Y(46), track_right, Y(56), n(5), fill="#1c1050", outline="", tags="ui")
        fill_width = int((track_right - track_left) * q["number"] / q["total"])
        if fill_width > 12:
            image = photo(("bar", fill_width, int(n(10))),
                          lambda: pill_png(fill_width, max(4, int(n(10))), VIOLET, BLUE, None, glossy=False))
            if image is not None:
                c.create_image(track_left, Y(51), image=image, anchor="w", tags="ui")
        self.pause_button_icon = IconButton(c, "pause", self.toggle_pause, size=int(n(44)))
        self.pause_button_icon.draw(X(898), Y(36))

        self.draw_dynamic(lay)
        self.ring.size = int(n(96))
        self.ring.draw(X(500), Y(112))

        category = q.get("category", "")
        if category:
            chip(c, X(500), Y(178), category.upper(), "#3a22a0", "#e6dcff", "ui", size=int(n(13)), pad=int(n(18)),
                 height=int(n(26)), anchor="center")
        glow_card(c, X(150), Y(290), X(850), Y(600), ("ui",), radius=n(32))
        # the question sits above the card; two lines at most, the font shrinks to fit
        draw_rich_text(c, X(500), Y(232), q["text"], n(880), sizes=tuple(int(n(v)) for v in (32, 29, 26, 23, 20)),
                       accent_words=2, max_lines=2)
        self.option_buttons = []
        if self.mode == "countdown":
            c.create_text(X(500), Y(443), text="Get ready…", font=font(n(36), True), fill=ACCENT, tags="ui")
        else:
            for i in range(4):
                state = self.option_state[i]
                style = "option" if state == "normal" else "disabled" if state == "gone" else state
                text = "" if state == "gone" else q["options"][i]
                mark = "check" if state == "correct" else "cross" if state == "wrong" else None
                button = self.button(lay, X(500), Y(341 + i * 66), text, lambda i=i: self.choose(i), style=style,
                                     width=640, height=54, size=20, badge=str(i + 1) if text or mark else " ",
                                     align="left")
                button.config(mark=mark, enabled=state == "normal" and not self.answered)
                self.option_buttons.append(button)

        bottom = Y(650)
        can_fifty = self.mode == "play" and not self.answered and self.lifeline.get(self.turn_player, False)
        self.fifty_button = self.button(lay, X(140), bottom, "50 : 50" if self.lifeline.get(self.turn_player) else "50 : 50  used",
                                        self.use_fifty, style="ghost", width=180, height=48, size=17)
        self.fifty_button.config(enabled=can_fifty)
        self.review_button = None
        if hasattr(self.game, "review_all"):
            has_previous = bool(self.game.review_all())
            self.review_button = self.button(lay, X(318), bottom, "Review", self.open_review, style="ghost", width=140,
                                             height=48, size=17)
            self.review_button.config(enabled=has_previous and self.mode == "play")
        last = q["number"] == q["total"]
        self.next_button = self.button(lay, X(860), bottom, "See Results" if last else "Next Question",
                                       self.next_question, style="gold", width=200, height=48, size=17)
        self.next_button.config(enabled=self.answered and self.mode == "play")
        if self.feedback:
            kind, word, sub = self.feedback
            fill = {"correct": "#0fa968", "wrong": "#d61f4d", "timeup": "#d97706"}[kind]
            chip(c, X(578), bottom, f"{word}   {sub}", fill, "#ffffff", "ui", size=int(n(16)), pad=int(n(20)),
                 height=int(n(40)), anchor="center")
        c.create_text(X(500), Y(700), text="1-4 answer   ·   Enter next   ·   H 50:50   ·   R review   ·   P pause   ·   M sound   ·   F11 fullscreen",
                      font=font(n(12), False), fill=DIM, tags="ui")

    # ---- the two seated players (left and right) and the sliding turn pill
    def begin_turn(self):
        """Called when a new player's turn starts: the spotlight slides to that player."""
        if self.mode == "countdown" or self.turn_player not in self.names:
            return
        idx = self.names.index(self.turn_player)
        self.turn_idx = idx
        self.act_from = list(self.act)
        self.act_to = [1.0 if j == idx else 0.0 for j in range(2)]
        self.pill_from = self.pill_x if self.pill_x is not None else (-90.0 if idx == 0 else 1090.0)
        self.pill_to = 200.0 if idx == 0 else 800.0
        self.turn_t0 = time.monotonic()
        if len(self.names) > 1:
            self.app.sound.play("swoosh")
        self.start_anim()

    def start_anim(self):
        if self.anim_job is None:
            self.anim_job = self.app.after(40, self.anim_step)

    def stop_anim(self):
        if self.anim_job is not None:
            self.app.after_cancel(self.anim_job)
            self.anim_job = None

    def anim_step(self):
        self.anim_job = None
        if self.app.current is not self:
            return
        now, busy = time.monotonic(), False
        if self.turn_t0 is not None:
            t = min(1.0, (now - self.turn_t0) / 0.6)
            e = 1 - (1 - t) ** 3
            self.act = [f + (g - f) * e for f, g in zip(self.act_from, self.act_to)]
            self.pill_prog = t
            self.pill_x = self.pill_from + (self.pill_to - self.pill_from) * e
            if t >= 1.0:
                self.turn_t0 = None
            busy = True
        for name in self.names:
            if self.bubble.get(name, ("", 0))[1] > now or self.bounce_until.get(name, 0) > now:
                busy = True
        if self.mode == "play" and not self.answered:
            busy = True         # the active player's screen keeps "typing"
        if self.mode in ("play", "countdown") and self.lay is not None:
            self.draw_dynamic(self.lay)
        if busy:
            self.anim_job = self.app.after(40, self.anim_step)

    def draw_dynamic(self, lay):
        c = self.canvas
        c.delete("dyn")
        if self.q is None:
            return
        for i in range(min(2, len(self.names))):
            self.draw_station(lay, i)
        self.draw_turn_pill(lay)
        c.tag_raise("fx")

    def draw_turn_pill(self, lay):
        if self.pill_x is None or self.turn_idx is None or self.mode == "countdown" or len(self.names) < 2:
            return
        c, n = self.canvas, lay.n
        name = self.names[self.turn_idx]
        x = lay.x(self.pill_x)
        y = lay.y(112) - n(42) * math.sin(math.pi * self.pill_prog)
        text = f"{shorten(name, 10)}'s turn"
        size, pad = int(n(16)), int(n(20))
        half = (ui_kit.text_width(text, size) + 2 * pad) / 2
        chip(c, x, y, text, GOLD, DARK_TEXT, ("ui", "dyn"), size=size, pad=pad, height=int(n(34)), anchor="center")
        tip = -1 if self.turn_idx == 0 else 1       # small arrow pointing at the player
        edge = x + tip * half
        c.create_polygon(edge + tip * n(14), y, edge + tip * n(1), y - n(8), edge + tip * n(1), y + n(8),
                         fill=GOLD, outline="", tags=("ui", "dyn"))

    def draw_station(self, lay, i):
        """One player sitting at a computer: a person behind a monitor, name, score and status."""
        c, X, Y, n = self.canvas, lay.x, lay.y, lay.n
        name = self.names[i]
        cx = X(68 if i == 0 else 932)
        a = max(0.0, min(1.0, self.act[i]))
        now = time.monotonic()
        tags = ("ui", "dyn")
        shirt = (VIOLET, PINK)[i]
        skin, hair = (("#f6cfa8", "#1b1038"), ("#e3aa83", "#3b1f14"))[i]

        def dim(color):
            return mix(BACKDROP_MID, color, 0.40 + 0.60 * a)

        glow_card(c, cx - n(64), Y(284), cx + n(64), Y(618), tags, radius=n(26), fill=mix(CARD_FILL, "#2a1a6a", a),
                  edge=mix("#3b2d8f", GOLD, a), glow=GOLD, rings=4, strength=0.55 * a)
        c.create_text(cx, Y(306), text=shorten(name, 9), font=font(n(17), True), fill=dim(TEXT), tags=tags)
        bubble_text, until = self.bubble.get(name, ("", 0))
        if bubble_text and until > now:
            fill = {"happy": "#0fa968", "sad": "#d61f4d"}.get(self.mood.get(name), "#0fa968")
            chip(c, cx, Y(334), bubble_text, fill, "#ffffff", tags, size=int(n(12)), pad=int(n(9)), height=int(n(24)),
                 anchor="center")
        elif a > 0.5:
            chip(c, cx, Y(334), "YOUR TURN", GOLD, DARK_TEXT, tags, size=int(n(11)), pad=int(n(10)), height=int(n(22)),
                 anchor="center")
        else:
            chip(c, cx, Y(334), "WAITING", "#1d1250", dim(MUTED), tags, size=int(n(11)), pad=int(n(10)),
                 height=int(n(22)), anchor="center")

        # the person
        mood = self.mood.get(name, "neutral")
        bounce = n(7) * abs(math.sin(now * 14)) if self.bounce_until.get(name, 0) > now and mood == "happy" else 0
        hy, r = Y(398) - bounce, n(23)
        if i == 1:      # longer hair behind the head
            round_rect(c, cx - n(27), hy - n(26), cx + n(27), hy + n(36), n(14), fill=dim(hair), outline="", tags=tags)
        round_rect(c, cx - n(36), hy + n(24), cx + n(36), hy + n(86), n(22), fill=dim(shirt), outline="", tags=tags)
        c.create_rectangle(cx - n(6), hy + n(16), cx + n(6), hy + n(28), fill=dim(skin), outline="", tags=tags)
        c.create_oval(cx - r, hy - r, cx + r, hy + r, fill=dim(skin), outline="", tags=tags)
        c.create_arc(cx - n(25), hy - n(26), cx + n(25), hy + n(14), start=0, extent=180, style="chord", fill=dim(hair),
                     outline="", tags=tags)
        for dx in (-8, 8):
            c.create_oval(cx + n(dx) - n(2.6), hy - n(2) - n(2.6), cx + n(dx) + n(2.6), hy - n(2) + n(2.6),
                          fill=dim("#1b1038"), outline="", tags=tags)
        mouth = dim("#7a2a3a")
        if mood == "happy":
            c.create_arc(cx - n(9), hy + n(2), cx + n(9), hy + n(18), start=200, extent=140, style="arc",
                         outline=mouth, width=max(2, n(2.4)), tags=tags)
        elif mood == "sad":
            c.create_arc(cx - n(8), hy + n(10), cx + n(8), hy + n(26), start=20, extent=140, style="arc",
                         outline=mouth, width=max(2, n(2.4)), tags=tags)
        else:
            c.create_line(cx - n(6), hy + n(11), cx + n(6), hy + n(11), fill=mouth, width=max(2, n(2.4)), tags=tags)

        # the computer in front of the person
        round_rect(c, cx - n(42), Y(446), cx + n(42), Y(502), n(8), fill=dim("#2a1d6b"), outline=dim("#6a58d6"), width=2, tags=tags)
        screen = mix("#120a35", shirt, 0.10 + 0.40 * a)
        round_rect(c, cx - n(37), Y(451), cx + n(37), Y(497), n(5), fill=screen, outline="", tags=tags)
        if a > 0.4:
            for k in range(3):
                length = n(44 - 10 * k) * (0.55 + 0.45 * abs(math.sin(now * 3.1 + k * 1.7)))
                c.create_line(cx - n(30), Y(463 + k * 11), cx - n(30) + length, Y(463 + k * 11),
                              fill=mix(screen, "#ffffff", 0.55), width=max(2, n(3)), capstyle="round", tags=tags)
        c.create_rectangle(cx - n(5), Y(502), cx + n(5), Y(514), fill=dim("#3a2d8f"), outline="", tags=tags)
        round_rect(c, cx - n(24), Y(513), cx + n(24), Y(520), n(3), fill=dim("#3a2d8f"), outline="", tags=tags)
        round_rect(c, cx - n(38), Y(526), cx + n(38), Y(538), n(5), fill=dim("#241a58"), outline=dim("#4b3aa8"), tags=tags)

        flashing = self.flash.get(name, 0) > now
        c.create_text(cx, Y(566), text=str(self.scores.get(name, 0)), font=font(n(34), True),
                      fill=GREEN if flashing else dim(TEXT), tags=tags)
        c.create_text(cx, Y(588), text="points", font=font(n(11), False), fill=dim(MUTED), tags=tags)
        streak = self.streak.get(name, 0)
        if streak >= 2:
            chip(c, cx, Y(606), f"x{streak} streak", "#5a2a10", ORANGE, tags, size=int(n(11)), pad=int(n(9)),
                 height=int(n(20)), anchor="center")

    # ---- pause and review overlays
    def draw_pause(self, lay):
        c, X, Y, n = self.canvas, lay.x, lay.y, lay.n
        glow_card(c, X(250), Y(200), X(750), Y(520), ("ui",), radius=n(34))
        draw_rich_text(c, X(500), Y(268), "Game paused", n(440), sizes=(int(n(44)),), accent_words=1, max_lines=1)
        c.create_text(X(500), Y(318), text="The timer is stopped. Take a breath!", font=font(n(18), False), fill=MUTED,
                      tags="ui")
        self.resume_button = self.button(lay, X(500), Y(392), "Resume", self.toggle_pause, width=360, height=60, size=22)
        self.quit_button = self.button(lay, X(500), Y(466), "Quit to menu", lambda: self.app.show("WelcomeScreen"),
                                       style="ghost", width=360, height=52, size=19)

    def draw_review(self, lay):
        c, X, Y, n = self.canvas, lay.x, lay.y, lay.n
        glow_card(c, X(110), Y(110), X(890), Y(600), ("ui",), radius=n(34))
        draw_rich_text(c, X(500), Y(166), "Previous questions", n(700), sizes=(int(n(38)),), accent_words=1, max_lines=1)
        total = len(self.review_list)
        c.create_text(X(500), Y(208), text=f"Newest first  ·  {self.review_index + 1} of {total}", font=font(n(16), False),
                      fill=MUTED, tags="ui")
        record = self.review_list[self.review_index]
        question = record["question"]
        if record["choice"] is None:
            given, color = "No answer (time ran out)", RED
        else:
            given, color = question["options"][record["choice"]], GREEN if record["correct"] else RED
        draw_rich_text(c, X(500), Y(290), question["text"], n(660), sizes=tuple(int(n(v)) for v in (26, 23, 20)),
                       accent_words=0, max_lines=3)
        c.create_text(X(170), Y(384), text=f"{record['player']} answered:   {given}", anchor="w", font=font(n(20), True),
                      fill=color, width=n(660), tags="ui")
        c.create_text(X(170), Y(432), text=f"Correct answer:   {question['options'][question['correct']]}", anchor="w",
                      font=font(n(20), True), fill=GREEN, width=n(660), tags="ui")
        self.older_button = self.button(lay, X(270), Y(530), "Older", self.review_older, style="ghost", width=170, height=48, size=17)
        self.older_button.config(enabled=self.review_index < total - 1)
        self.newer_button = self.button(lay, X(460), Y(530), "Newer", self.review_newer, style="ghost", width=170, height=48, size=17)
        self.newer_button.config(enabled=self.review_index > 0)
        self.close_button = self.button(lay, X(700), Y(530), "Close", self.close_review, style="gold", width=220, height=52, size=19)

    def open_review(self):
        if self.mode != "play" or not hasattr(self.game, "review_all"):
            return
        records = self.game.review_all()
        if not records:
            return
        self.review_list, self.review_index = records, 0
        self.hold_timer()
        self.mode = "review"
        self.app.redraw()

    def review_older(self):
        if self.mode == "review" and self.review_index < len(self.review_list) - 1:
            self.review_index += 1
            self.app.redraw()

    def review_newer(self):
        if self.mode == "review" and self.review_index > 0:
            self.review_index -= 1
            self.app.redraw()

    def close_review(self):
        if self.mode == "review":
            self.mode = "play"
            self.release_timer()
            self.app.redraw()

    def toggle_pause(self):
        if self.mode == "play":
            self.hold_timer()
            self.mode = "pause"
        elif self.mode == "pause":
            self.mode = "play"
            self.release_timer()
        else:
            return
        self.app.redraw()

    # ---- timer
    def start_timer(self):
        self.stop_timer()
        self.held = False
        if QUESTION_TIME <= 0:
            return
        self.deadline = time.monotonic() + QUESTION_TIME
        self.tick()

    def tick(self):
        self.remaining = max(0.0, self.deadline - time.monotonic())
        self.ring.set(self.remaining, QUESTION_TIME)
        whole = int(self.remaining) + 1
        if 0 < self.remaining <= 3 and whole != self.last_tick:
            self.app.sound.play("tick")
        self.last_tick = whole
        if self.remaining <= 0:
            self.timer_job = None
            self.time_up()
            return
        self.timer_job = self.app.after(100, self.tick)

    def stop_timer(self):
        if self.timer_job is not None:
            self.app.after_cancel(self.timer_job)
            self.timer_job = None

    def hold_timer(self):
        """Stop the clock for a pause or review, remembering how much time was left."""
        if self.timer_job is not None:
            self.held_left = max(0.0, self.deadline - time.monotonic())
            self.stop_timer()
            self.held = True

    def release_timer(self):
        if self.held:
            self.held = False
            self.deadline = time.monotonic() + self.held_left
            self.tick()

    # ---- answering
    def choose(self, index):
        if self.mode == "play" and not self.answered and index not in self.hidden:
            self.lock_answer(index, time_up=False)

    def time_up(self):
        if not self.answered:
            self.lock_answer(None, time_up=True)

    def use_fifty(self):
        """50:50 lifeline: hide two wrong answers (once per player per game)."""
        player = self.turn_player
        if self.mode != "play" or self.answered or not self.lifeline.get(player):
            return
        right = self.q["correct"]
        self.hidden = set(random.sample([i for i in range(4) if i != right], 2))
        for i in self.hidden:
            self.option_state[i] = "gone"
        self.lifeline[player] = False
        self.app.sound.play("click")
        self.app.redraw()

    def lock_answer(self, index, time_up):
        self.answered = True
        self.stop_timer()
        game = self.game
        player = game.current_player()
        before = game.scores[player]
        right = game.current_question()["correct"]
        is_correct = game.submit_answer(index)
        gained = game.scores[player] - before
        speed = (self.remaining / QUESTION_TIME) if QUESTION_TIME > 0 else 0.5
        self.picked, self.right = index, right
        for i in range(4):
            if i == right:
                self.option_state[i] = "correct"
            elif i == index:
                self.option_state[i] = "wrong"
            else:
                self.option_state[i] = "gone" if i in self.hidden else "dim"
        self.scores[player] = game.scores[player]
        lay = self.app.layout()
        fx = self.app.effects
        cx, cy = lay.x(500), lay.y(443)
        if time_up:
            self.streak[player] = 0
            self.feedback = ("timeup", "Time's up!", "Be quicker next time")
            self.app.sound.play("timeup")
            self.react(player, "sad", "Time's up!")
            fx.banner(cx, cy, "Time's up!", ORANGE, size=int(lay.n(84)), shake=True, hold=700)
        elif is_correct:
            self.streak[player] = self.streak.get(player, 0) + 1
            self.best[player] = max(self.best.get(player, 0), self.streak[player])
            word, color = cheer_for(self.streak[player], speed, self.last_word)
            self.last_word = word
            streak = self.streak[player]
            extra = f"  ·  {streak} in a row" if streak >= 2 else ""
            self.feedback = ("correct", word, f"+{gained} points{extra}")
            self.flash[player] = time.monotonic() + 0.9
            self.app.after(950, self._end_flash)
            self.app.sound.play("correct")
            fx.banner(cx, cy, word, color, sub=f"{player}  +{gained}{extra}", size=int(lay.n(min(100, 1150 / len(word)))),
                      hold=900)
            card_x = lay.x(68 if self.names.index(player) == 0 else 932)
            self.react(player, "happy", word)
            fx.float_text(card_x, lay.y(520), f"+{gained}", GREEN, size=int(lay.n(30)))
            fx.burst(cx, cy, count=30 if streak < 3 else 55, power=11)
            fx.burst(card_x, lay.y(398), count=18, power=8)
        else:
            self.streak[player] = 0
            word = random.choice(WRONG_WORDS)
            self.feedback = ("wrong", word, f"Answer: {shorten(self.q['options'][right], 24)}")
            self.app.sound.play("wrong")
            self.react(player, "sad", word)
            fx.banner(cx, cy, word, PINK, size=int(lay.n(84)), shake=True, hold=600)
        self.app.redraw()

    def react(self, player, mood, text):
        """The seated player smiles (or frowns), bounces and says a short word."""
        now = time.monotonic()
        self.mood[player] = mood
        self.bubble[player] = (text, now + 1.8)
        self.bounce_until[player] = now + (0.9 if mood == "happy" else 0)
        self.start_anim()

    def _end_flash(self):
        if self.app.current is self:
            self.app.redraw()

    def next_question(self):
        if not self.answered or self.mode != "play":
            return
        if self.game.next_question():
            self.app.effects.cancel()
            self.render_question()
            self.start_timer()
            self.app.redraw()
        else:
            self.app.finish_game()

    def on_key(self, event):
        key = (event.char or "").lower()
        if self.mode == "countdown":
            return
        if self.mode == "review":
            if event.keysym in ("Escape", "Return", "space") or key == "r":
                self.close_review()
            elif event.keysym in ("Left", "Down"):
                self.review_older()
            elif event.keysym in ("Right", "Up"):
                self.review_newer()
            return
        if key == "p" or event.keysym == "Escape":
            self.toggle_pause()
            return
        if self.mode == "pause":
            if event.keysym in ("Return", "space"):
                self.toggle_pause()
            return
        if not self.answered:
            if key in ("a", "b", "c", "d"):
                self.choose("abcd".index(key))
            elif key in ("1", "2", "3", "4"):
                self.choose(int(key) - 1)
            elif key == "h":
                self.use_fifty()
        elif event.keysym in ("Return", "space", "Right"):
            self.next_question()
        if key == "r":
            self.open_review()


# ---------------------------------------------------------------------- Results
def draw_trophy(c, cx, cy, s):
    """A golden trophy built from simple shapes."""
    gold, light, dark = GOLD, "#fff0a8", "#c98a0d"
    tags = "ui"
    for sign in (-1, 1):
        c.create_arc(cx + sign * 56 * s - 26 * s, cy - 44 * s, cx + sign * 56 * s + 26 * s, cy - 2 * s, start=90 if sign < 0 else -90,
                     extent=180, style="arc", outline=dark, width=max(3, 7 * s), tags=tags)
    c.create_polygon(cx - 42 * s, cy - 54 * s, cx + 42 * s, cy - 54 * s, cx + 36 * s, cy - 6 * s, cx + 18 * s, cy + 18 * s,
                     cx - 18 * s, cy + 18 * s, cx - 36 * s, cy - 6 * s, fill=gold, outline=dark, width=2, smooth=False, tags=tags)
    c.create_polygon(cx - 34 * s, cy - 50 * s, cx - 20 * s, cy - 50 * s, cx - 24 * s, cy - 6 * s, cx - 30 * s, cy - 8 * s,
                     fill=light, outline="", tags=tags)
    c.create_polygon(star_points(cx, cy - 26 * s, 17 * s, 5, 0.45), fill="#fff7cf", outline="", tags=tags)
    c.create_rectangle(cx - 7 * s, cy + 18 * s, cx + 7 * s, cy + 36 * s, fill=gold, outline=dark, tags=tags)
    round_rect(c, cx - 32 * s, cy + 36 * s, cx + 32 * s, cy + 52 * s, 5 * s, fill=dark, outline="#fff0a8", width=2, tags=tags)


class ResultsScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.infos = []
        self.headline = ""
        self.subtitle = ""
        self.tie = False
        self.solo = False
        self.progress = 1.0
        self.count_job = None
        self.lay = None

    def on_show(self):
        results = self.app.results
        quiz = self.app.screens["QuizScreen"]
        self.tie = results["is_tie"]
        self.solo = len(results["scores"]) == 1
        self.infos = []
        for name in results["scores"]:
            correct, wrong = results["correct"][name], results["wrong"][name]
            total = correct + wrong
            self.infos.append({
                "name": name, "score": results["scores"][name], "correct": correct, "wrong": wrong,
                "accuracy": round(100 * correct / total) if total else 0,
                "best_streak": quiz.best.get(name, 0),
                "label": "YOUR SCORE" if self.solo else "TIE" if self.tie else "WINNER" if name == results["winner"] else "RUNNER-UP",
            })
        if self.solo:
            info = self.infos[0]
            self.headline = f"Well played, {shorten(info['name'], 12)}!"
            accuracy = info["accuracy"]
            self.subtitle = ("Perfect score!" if accuracy == 100 else "Great game!" if accuracy >= 70
                             else "Good effort!" if accuracy >= 50 else "Keep practising, you will get there!")
            if accuracy >= 70:
                self.app.effects.confetti(self.app.layout().w)
            self.app.sound.play("win" if accuracy >= 50 else "tie")
        elif self.tie:
            self.headline, self.subtitle = "It's a tie!", "Evenly matched. Play again to break it!"
            self.app.sound.play("tie")
        else:
            winner = next(info for info in self.infos if info["label"] == "WINNER")
            self.headline = f"{winner['name']} wins!"
            accuracy = winner["accuracy"]
            self.subtitle = ("Outstanding performance!" if accuracy >= 90 else "Great game!" if accuracy >= 70
                             else "Well played!" if accuracy >= 50 else "A hard-fought win!")
            self.app.effects.confetti(self.app.layout().w)
            self.app.sound.play("win")
        self.progress = 0.0
        self.started = time.monotonic()
        self.count_job = self.app.after(30, self.count_up)

    def on_hide(self):
        if self.count_job is not None:
            self.app.after_cancel(self.count_job)
            self.count_job = None

    def count_up(self):
        t = (time.monotonic() - self.started) / 1.0
        self.progress = min(1.0, t)
        self.draw_scores()
        self.count_job = self.app.after(30, self.count_up) if t < 1.0 else None

    def card_box(self, lay, i):
        left, right = (300, 700) if self.solo else ((100, 475), (525, 900))[i]
        return lay.x(left), lay.x(right), lay.y(272), lay.y(602)

    def draw_scores(self):
        lay = self.lay
        if lay is None:
            return
        c = self.canvas
        c.delete("score")
        for i, info in enumerate(self.infos[:2]):
            x1, x2, y1, _ = self.card_box(lay, i)
            winner = info["label"] in ("WINNER", "TIE", "YOUR SCORE")
            shown = round(info["score"] * (1 - (1 - self.progress) ** 3))
            c.create_text((x1 + x2) / 2, y1 + lay.n(150), text=str(shown), font=font(lay.n(70), True),
                          fill=GOLD if winner else TEXT, tags=("ui", "score"))

    def draw(self, lay):
        self.lay = lay
        c, X, Y, n = self.canvas, lay.x, lay.y, lay.n
        cx = X(500)
        if self.tie:
            c.create_oval(cx - n(46), Y(96) - n(46), cx + n(46), Y(96) + n(46), outline=GOLD, width=n(7), tags="ui")
            c.create_text(cx, Y(94), text="=", font=font(n(64), True), fill=GOLD, tags="ui")
        else:
            draw_trophy(c, cx, Y(98), n(1.1))
        draw_rich_text(c, cx, Y(190), self.headline, n(800), sizes=(int(n(56)), int(n(46)), int(n(38))), accent_words=1,
                       max_lines=1)
        c.create_text(cx, Y(238), text=self.subtitle, font=font(n(21), False), fill=MUTED, tags="ui")
        for i, info in enumerate(self.infos[:2]):
            self.draw_card(lay, info, i)
        self.draw_scores()
        self.play_again_button = self.button(lay, X(330), Y(660), "Play Again", self.app.play_again, style="gold",
                                             width=300, height=58, size=21)
        self.home_button = self.button(lay, X(670), Y(660), "Return to Home", lambda: self.app.show("WelcomeScreen"),
                                       style="ghost", width=300, height=58, size=21)

    def draw_card(self, lay, info, i):
        c, n = self.canvas, lay.n
        winner = info["label"] in ("WINNER", "TIE", "YOUR SCORE")
        x1, x2, y1, y2 = self.card_box(lay, i)
        middle = (x1 + x2) / 2
        glow_card(c, x1, y1, x2, y2, ("ui",), radius=n(32), edge=GOLD if winner else "#6f72ff", glow=GOLD if winner else "#6c3df0",
                  fill="#21124f" if winner else CARD_FILL)
        chip(c, middle, y1 + n(32), info["label"], GOLD if winner else "#2a1a7a", DARK_TEXT if winner else "#cdbfff", "ui",
             size=int(n(13)), pad=int(n(16)), height=int(n(26)), anchor="center")
        c.create_text(middle, y1 + n(82), text=shorten(info["name"], 14), font=font(n(30), True), fill=TEXT, tags="ui")
        c.create_text(middle, y1 + n(200), text="points", font=font(n(15), False), fill=MUTED, tags="ui")
        c.create_text(middle, y1 + n(232), text=f"Correct {info['correct']}   ·   Incorrect {info['wrong']}",
                      font=font(n(17), False), fill=TEXT, tags="ui")
        bar_left, bar_right = x1 + n(40), x2 - n(40)
        round_rect(c, bar_left, y1 + n(255), bar_right, y1 + n(267), n(6), fill="#1c1050", outline="", tags="ui")
        width = int((bar_right - bar_left) * info["accuracy"] / 100)
        if width > 12:
            image = photo(("bar", width, int(n(12)), winner),
                          lambda: pill_png(width, max(4, int(n(12))), GOLD if winner else VIOLET, GOLD_LIGHT if winner else BLUE,
                                           None, glossy=False))
            if image is not None:
                c.create_image(bar_left, y1 + n(261), image=image, anchor="w", tags="ui")
        c.create_text(middle, y1 + n(288), text=f"Accuracy {info['accuracy']}%", font=font(n(15), False), fill=MUTED, tags="ui")
        c.create_text(middle, y1 + n(311), text=f"Best streak: {info['best_streak']} in a row", font=font(n(15), False),
                      fill=ORANGE if info["best_streak"] >= 2 else MUTED, tags="ui")


GOLD_LIGHT = ui_kit.GOLD_LIGHT
