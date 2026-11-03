"""Tests for database.py (uses a temporary database file). Run: python test_database.py"""
import os, tempfile, unittest
os.environ["QUIZ_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")
import database


class DatabaseTests(unittest.TestCase):
    def setUp(self):                            # every test gets its own empty database file
        database.DB_PATH = os.path.join(tempfile.mkdtemp(), "test.db")
        database.init_db()

    def test_starter_questions_loaded_once(self):
        database.init_db()                      # a second call must not duplicate anything
        self.assertGreaterEqual(len(database.get_questions(100)), 20)
        self.assertEqual(len(database.get_questions(100)), len(database.STARTER_QUESTIONS))

    def test_question_shape_and_correct_index(self):
        originals = {t: (o, c) for _, t, o, c in database.STARTER_QUESTIONS}
        for q in database.get_questions(100):
            self.assertEqual(len(q["options"]), 4)
            options, correct = originals[q["text"]]
            self.assertEqual(q["options"][q["correct"]], options[correct])   # shuffle keeps the right answer

    def test_count_and_category(self):
        self.assertEqual(len(database.get_questions(5)), 5)
        self.assertTrue(all(q["category"] == "Stack" for q in database.get_questions(50, "Stack")))

    def test_add_question_validation(self):
        qid = database.add_question("Test", "What is 1+1?", ["1", "2", "3", "4"], 1)
        self.assertIsInstance(qid, int)
        with self.assertRaises(ValueError):
            database.add_question("Test", "Bad", ["a", "a", "b", "c"], 0)

    def test_results_and_leaderboard(self):
        database.save_result("Nisha", 30, 3, 1)
        database.save_result("nisha", 20, 2, 2)
        database.save_result("Kajal", 40, 4, 0)
        board = database.get_leaderboard()
        self.assertEqual(board[0]["total_score"], 50)       # Nisha + nisha are one player
        self.assertEqual(board[0]["games"], 2)
        self.assertEqual(board[1]["player"], "Kajal")


if __name__ == "__main__":
    unittest.main()
