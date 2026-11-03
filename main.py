"""main.py: starts the game. Questions come from SQLite (database.py) and results are saved there."""
from gui import App
from game import QuizGame
import database

database.init_db()      # creates quiz_battle.db and the starter questions on the first run

QUESTIONS_PER_GAME = 10


def make_game(players):
    return QuizGame(players, database.get_questions(QUESTIONS_PER_GAME))


def on_finish(results):
    for name in results["scores"]:
        database.save_result(name, results["scores"][name], results["correct"][name], results["wrong"][name])


if __name__ == "__main__":
    App(make_game, on_finish).mainloop()
