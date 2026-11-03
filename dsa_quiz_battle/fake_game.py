"""fake_game.py: a stand-in for the real QuizGame, so the GUI can be built and tested alone.

It has the SAME functions and results as the real `game.QuizGame` (see the Team Plan's
"Teeno hisson ka contract"), but it is deliberately simple: no queue, no stack.
When your friend's game.py is ready, main.py switches to the real one and this file
is no longer used.
"""

POINTS_PER_CORRECT = 10

# Same shape the database will give: options is a list of 4, correct is an index 0-3.
SAMPLE_QUESTIONS = [
    {"id": 1, "category": "Stack", "text": "Which data structure follows the LIFO principle?",
     "options": ["Queue", "Stack", "Array", "Tree"], "correct": 1},
    {"id": 2, "category": "Queue", "text": "Which data structure follows the FIFO principle?",
     "options": ["Stack", "Graph", "Queue", "Heap"], "correct": 2},
    {"id": 3, "category": "Complexity", "text": "What is the time complexity of binary search?",
     "options": ["O(n)", "O(n log n)", "O(1)", "O(log n)"], "correct": 3},
    {"id": 4, "category": "Hashing", "text": "Which Python type is a hash map?",
     "options": ["dict", "list", "tuple", "str"], "correct": 0},
]


class FakeGame:
    def __init__(self, players, questions=None):
        self.players = list(players)
        self.questions = list(questions or SAMPLE_QUESTIONS)
        self.restart()

    def restart(self):
        self.index = 0
        self.turn = 0
        self.scores = {p: 0 for p in self.players}
        self.correct_count = {p: 0 for p in self.players}
        self.wrong_count = {p: 0 for p in self.players}

    def current_question(self):
        """The question dict from the database plus 'number' (1-based) and 'total'."""
        q = dict(self.questions[self.index])
        q["number"] = self.index + 1
        q["total"] = len(self.questions)
        return q

    def current_player(self):
        return self.players[self.turn % len(self.players)]

    def submit_answer(self, choice):
        """choice is 0-3, or None when the time ran out. Returns True if correct."""
        player = self.current_player()
        correct = choice == self.questions[self.index]["correct"]
        if correct:
            self.scores[player] += POINTS_PER_CORRECT
            self.correct_count[player] += 1
        else:
            self.wrong_count[player] += 1
        return correct

    def next_question(self):
        """Move on. Returns False when there are no more questions."""
        self.index += 1
        self.turn += 1
        return self.index < len(self.questions)

    def is_finished(self):
        return self.index >= len(self.questions)

    def get_results(self):
        top = max(self.scores.values())
        leaders = [p for p, s in self.scores.items() if s == top]
        is_tie = len(leaders) > 1
        return {
            "scores": dict(self.scores),
            "correct": dict(self.correct_count),
            "wrong": dict(self.wrong_count),
            "winner": None if is_tie else leaders[0],
            "is_tie": is_tie,
        }
