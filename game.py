"""game.py: the game logic (the Backend).

There is NO tkinter in this file: it only holds the quiz rules, so it can be tested
without any window (see test_game.py).

The four data structures from the project documentation, and where each one is used:

    List        -> the questions, each question's 4 options, and the history records
    Queue       -> the order of the questions (self.queue, a collections.deque, FIFO)
    Dictionary  -> player name -> score, and the correct / wrong counts
    Stack       -> questions already left behind, for Back / Review (self.history, LIFO)
"""
import random
from collections import deque

POINTS_PER_CORRECT = 10


class QuizGame:
    def __init__(self, players, questions, shuffle=True):
        """players: list of names. questions: list of dicts, each like
        {"id": 1, "category": "Stack", "text": "...", "options": [4 texts], "correct": 0-3}
        """
        self.players = list(players)
        self.all_questions = list(questions)    # LIST: every question the game was given
        self.shuffle = shuffle
        self.restart()

    # ------------------------------------------------------------------ setup
    def restart(self):
        """Start a fresh game with the same players (used by Play Again)."""
        order = self.all_questions[:]           # copy, so the original list is never changed
        if self.shuffle:
            random.shuffle(order)
        self.queue = deque(order)               # QUEUE: first question added = first shown (FIFO)
        self.total = len(order)
        self.history = []                       # STACK: questions already answered (LIFO)
        self.scores = {p: 0 for p in self.players}          # DICTIONARY: name -> score
        self.correct_count = {p: 0 for p in self.players}   # DICTIONARY: name -> number correct
        self.wrong_count = {p: 0 for p in self.players}     # DICTIONARY: name -> number wrong
        self.turn = 0                           # whose turn it is (index into self.players)
        self.current_record = None              # the answer given to the current question

    # --------------------------------------------------------------- questions
    def current_question(self):
        """The question at the FRONT of the queue (peek: it is not removed yet).
        Returns a dict with text, options, correct, plus 'number' (1-based) and 'total'.
        Returns None when there are no questions left.
        """
        if not self.queue:
            return None
        question = dict(self.queue[0])          # peek at the front of the queue
        question["number"] = self.total - len(self.queue) + 1
        question["total"] = self.total
        return question

    def current_player(self):
        """Players take turns: question 1 -> player 1, question 2 -> player 2, and so on."""
        return self.players[self.turn % len(self.players)]

    def submit_answer(self, choice):
        """The current player answers. choice is 0-3, or None if the time ran out.
        Returns True if correct, False if wrong. A second answer to the same question is ignored.
        """
        if self.current_record is not None:     # already answered this question
            return self.current_record["correct"]
        question = self.queue[0]
        player = self.current_player()
        correct = choice == question["correct"]
        if correct:
            self.scores[player] += POINTS_PER_CORRECT
            self.correct_count[player] += 1
        else:
            self.wrong_count[player] += 1
        self.current_record = {"question": question, "player": player,
                               "choice": choice, "correct": correct}
        return correct

    def next_question(self):
        """Finish the current question and move on.
        popleft() removes the front of the queue (dequeue), and the answered question is
        pushed on top of the stack. Returns False when there are no more questions.
        """
        if self.current_record is None:
            raise RuntimeError("Answer the current question before moving on.")
        self.queue.popleft()                    # QUEUE: dequeue from the front
        self.history.append(self.current_record)  # STACK: push
        self.current_record = None
        self.turn += 1
        return bool(self.queue)

    def is_finished(self):
        return not self.queue                   # an empty queue means the quiz is over

    # ----------------------------------------------------------- Back / Review
    def review_previous(self):
        """Look at the previous question (top of the stack) without changing anything.
        Returns {"question", "player", "choice", "correct"} or None if there is none yet.
        """
        return self.history[-1] if self.history else None

    def review_all(self):
        """Every answered question, newest first (this is LIFO order: last in, first out)."""
        return list(reversed(self.history))

    # ----------------------------------------------------------------- results
    def get_results(self):
        top_score = max(self.scores.values())
        leaders = [name for name, score in self.scores.items() if score == top_score]
        is_tie = len(leaders) > 1
        return {
            "scores": dict(self.scores),
            "correct": dict(self.correct_count),
            "wrong": dict(self.wrong_count),
            "winner": None if is_tie else leaders[0],
            "is_tie": is_tie,
        }
