"""test_game.py: checks game.py without any window.

Run with:  python test_game.py
"""
import unittest

from game import QuizGame, POINTS_PER_CORRECT


def make_questions(count=4):
    # Question i has its correct answer at index i % 4.
    return [{"id": i, "category": "Test", "text": f"Question {i}?",
             "options": ["a", "b", "c", "d"], "correct": i % 4} for i in range(count)]


def new_game(count=4, players=("Nisha", "Kajal")):
    return QuizGame(list(players), make_questions(count), shuffle=False)


class QuizGameTests(unittest.TestCase):
    def test_start_state(self):
        game = new_game()
        self.assertEqual(len(game.queue), 4)
        self.assertEqual(game.scores, {"Nisha": 0, "Kajal": 0})
        self.assertFalse(game.is_finished())
        self.assertEqual(game.current_player(), "Nisha")

    def test_queue_gives_questions_in_order(self):
        game = new_game()
        seen = []
        while True:
            seen.append(game.current_question()["id"])
            game.submit_answer(None)
            if not game.next_question():
                break
        self.assertEqual(seen, [0, 1, 2, 3])        # FIFO: first in, first out

    def test_question_numbers(self):
        game = new_game()
        q = game.current_question()
        self.assertEqual((q["number"], q["total"]), (1, 4))
        game.submit_answer(0)
        game.next_question()
        q = game.current_question()
        self.assertEqual((q["number"], q["total"]), (2, 4))

    def test_correct_answer_scores(self):
        game = new_game()
        self.assertTrue(game.submit_answer(0))      # question 0: correct is index 0
        self.assertEqual(game.scores["Nisha"], POINTS_PER_CORRECT)
        self.assertEqual(game.correct_count["Nisha"], 1)

    def test_wrong_answer_scores_zero(self):
        game = new_game()
        self.assertFalse(game.submit_answer(3))
        self.assertEqual(game.scores["Nisha"], 0)
        self.assertEqual(game.wrong_count["Nisha"], 1)

    def test_no_answer_counts_as_wrong(self):
        game = new_game()
        self.assertFalse(game.submit_answer(None))  # time ran out
        self.assertEqual(game.wrong_count["Nisha"], 1)

    def test_second_answer_is_ignored(self):
        game = new_game()
        game.submit_answer(0)
        game.submit_answer(1)
        self.assertEqual(game.scores["Nisha"], POINTS_PER_CORRECT)
        self.assertEqual(game.wrong_count["Nisha"], 0)

    def test_players_take_turns(self):
        game = new_game()
        names = []
        for _ in range(4):
            names.append(game.current_player())
            game.submit_answer(None)
            game.next_question()
        self.assertEqual(names, ["Nisha", "Kajal", "Nisha", "Kajal"])

    def test_cannot_skip_a_question(self):
        game = new_game()
        with self.assertRaises(RuntimeError):
            game.next_question()

    def test_finishes_after_last_question(self):
        game = new_game(count=2)
        game.submit_answer(0)
        self.assertTrue(game.next_question())
        self.assertFalse(game.is_finished())
        game.submit_answer(1)
        self.assertFalse(game.next_question())      # no more questions
        self.assertTrue(game.is_finished())
        self.assertIsNone(game.current_question())

    def test_winner(self):
        game = new_game()
        for _ in range(4):                          # Nisha always right, Kajal always wrong
            q = game.current_question()
            if game.current_player() == "Nisha":
                game.submit_answer(q["correct"])
            else:
                game.submit_answer((q["correct"] + 1) % 4)
            game.next_question()
        result = game.get_results()
        self.assertEqual(result["winner"], "Nisha")
        self.assertFalse(result["is_tie"])
        self.assertEqual(result["scores"], {"Nisha": 2 * POINTS_PER_CORRECT, "Kajal": 0})
        self.assertEqual(result["correct"], {"Nisha": 2, "Kajal": 0})
        self.assertEqual(result["wrong"], {"Nisha": 0, "Kajal": 2})

    def test_tie(self):
        game = new_game()
        for _ in range(4):                          # everyone answers correctly: equal scores
            game.submit_answer(game.current_question()["correct"])
            game.next_question()
        result = game.get_results()
        self.assertTrue(result["is_tie"])
        self.assertIsNone(result["winner"])

    def test_review_previous_uses_the_stack(self):
        game = new_game()
        self.assertIsNone(game.review_previous())   # nothing answered before the first question
        game.submit_answer(2)                       # wrong, question 0
        game.next_question()
        game.submit_answer(1)                       # correct, question 1
        game.next_question()
        previous = game.review_previous()           # top of the stack = question 1
        self.assertEqual(previous["question"]["id"], 1)
        self.assertEqual(previous["player"], "Kajal")
        self.assertTrue(previous["correct"])
        newest_first = [r["question"]["id"] for r in game.review_all()]
        self.assertEqual(newest_first, [1, 0])      # LIFO order

    def test_restart(self):
        game = new_game()
        game.submit_answer(0)
        game.next_question()
        game.restart()
        self.assertEqual(game.scores, {"Nisha": 0, "Kajal": 0})
        self.assertEqual(len(game.queue), 4)
        self.assertEqual(game.history, [])
        self.assertEqual(game.current_player(), "Nisha")

    def test_shuffle_keeps_all_questions(self):
        game = QuizGame(["A", "B"], make_questions(10), shuffle=True)
        ids = sorted(q["id"] for q in game.queue)
        self.assertEqual(ids, list(range(10)))

    def test_original_questions_are_not_changed(self):
        questions = make_questions(4)
        game = QuizGame(["A", "B"], questions, shuffle=True)
        game.submit_answer(None)
        game.next_question()
        self.assertEqual([q["id"] for q in questions], [0, 1, 2, 3])


if __name__ == "__main__":
    unittest.main(verbosity=2)
