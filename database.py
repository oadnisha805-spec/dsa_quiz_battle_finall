"""database.py: the SQLite database (the Database part). Only the standard library is used.

Tables:
    questions(id, category, text, opt0, opt1, opt2, opt3, correct)
    results(id, player, score, correct, wrong, played_at)

Functions used by main.py:
    init_db()                 -> create the tables and add the starter questions (first run only)
    get_questions(count)      -> list of question dicts, random order, options shuffled
    save_result(player, score, correct, wrong)
    get_leaderboard(limit)    -> best players, highest total score first
"""
import os
import random
import sqlite3
import sys
from datetime import datetime

# When the game is packed into an .exe, keep the database next to the .exe (not in a temporary folder).
_HOME = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("QUIZ_DB", os.path.join(_HOME, "quiz_battle.db"))

# (category, question, [4 options], index of the correct option)
STARTER_QUESTIONS = [
    ("Stack", "Which data structure follows the LIFO principle?", ["Queue", "Stack", "Array", "Tree"], 1),
    ("Stack", "Which operation adds an item to the top of a stack?", ["pop", "peek", "push", "enqueue"], 2),
    ("Stack", "Which problem is a classic use of a stack?", ["Balancing brackets", "Shortest path", "Sorting names", "Hashing keys"], 0),
    ("Stack", "What does peek() do on a stack?", ["Removes the top item", "Reads the top item without removing it", "Clears the stack", "Adds an item"], 1),
    ("Queue", "Which data structure follows the FIFO principle?", ["Stack", "Graph", "Queue", "Heap"], 2),
    ("Queue", "Which operation removes an item from the front of a queue?", ["push", "dequeue", "enqueue", "peek"], 1),
    ("Queue", "Which Python class gives a fast queue with popleft()?", ["collections.deque", "set", "tuple", "str"], 0),
    ("Queue", "A printer waiting list is an example of which structure?", ["Stack", "Tree", "Queue", "Graph"], 2),
    ("Complexity", "What is the time complexity of binary search?", ["O(n)", "O(n log n)", "O(1)", "O(log n)"], 3),
    ("Complexity", "What is the time complexity of reading array[i]?", ["O(1)", "O(n)", "O(log n)", "O(n^2)"], 0),
    ("Complexity", "Which sorting algorithm has O(n log n) time in the average case?", ["Bubble sort", "Insertion sort", "Merge sort", "Selection sort"], 2),
    ("Complexity", "What is the worst-case time of linear search in a list of n items?", ["O(1)", "O(log n)", "O(n)", "O(n^2)"], 2),
    ("Hashing", "Which Python type is a hash map?", ["dict", "list", "tuple", "str"], 0),
    ("Hashing", "What happens when two keys get the same hash index?", ["A collision", "An overflow", "A deadlock", "A rotation"], 0),
    ("Hashing", "What is the average time to look up a key in a hash table?", ["O(n)", "O(1)", "O(log n)", "O(n log n)"], 1),
    ("Array", "Array indexes in Python start at which number?", ["1", "0", "-1", "2"], 1),
    ("Array", "Which structure stores items in contiguous memory?", ["Linked list", "Array", "Tree", "Graph"], 1),
    ("Linked List", "Each node of a singly linked list holds data and what else?", ["A pointer to the next node", "A hash key", "The array size", "A sorted copy"], 0),
    ("Linked List", "Inserting at the head of a linked list takes how long?", ["O(1)", "O(n)", "O(log n)", "O(n^2)"], 0),
    ("Tree", "In a binary tree, each node has at most how many children?", ["1", "2", "3", "4"], 1),
    ("Tree", "Which traversal of a binary search tree gives sorted order?", ["Preorder", "Postorder", "Inorder", "Level order"], 2),
    ("Tree", "What is the top node of a tree called?", ["Leaf", "Root", "Parent", "Edge"], 1),
    ("Graph", "Which algorithm explores a graph level by level?", ["Depth-first search", "Breadth-first search", "Binary search", "Quick sort"], 1),
    ("Graph", "Which data structure does BFS use?", ["Stack", "Queue", "Heap", "Set"], 1),
    ("Sorting", "Which sorting algorithm repeatedly swaps neighbouring items that are in the wrong order?", ["Merge sort", "Quick sort", "Bubble sort", "Heap sort"], 2),
    ("Recursion", "What every recursive function needs to stop is called?", ["A base case", "A loop", "A pointer", "A hash"], 0),
]


def connect():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the tables if they are missing and fill the questions the first time."""
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT NOT NULL, text TEXT NOT NULL UNIQUE,
            opt0 TEXT NOT NULL, opt1 TEXT NOT NULL, opt2 TEXT NOT NULL, opt3 TEXT NOT NULL,
            correct INTEGER NOT NULL CHECK (correct BETWEEN 0 AND 3))""")
        db.execute("""CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT, player TEXT NOT NULL, score INTEGER NOT NULL,
            correct INTEGER NOT NULL, wrong INTEGER NOT NULL, played_at TEXT NOT NULL)""")
        for category, text, options, correct in STARTER_QUESTIONS:
            db.execute("INSERT OR IGNORE INTO questions (category, text, opt0, opt1, opt2, opt3, correct) "
                       "VALUES (?, ?, ?, ?, ?, ?, ?)", (category, text, *options, correct))


def add_question(category, text, options, correct):
    """Add one question (returns its id). Raises ValueError if it is not valid."""
    if len(options) != 4 or len(set(options)) != 4 or not 0 <= correct <= 3 or not text.strip():
        raise ValueError("A question needs text, 4 different options and a correct index 0-3.")
    with connect() as db:
        cursor = db.execute("INSERT INTO questions (category, text, opt0, opt1, opt2, opt3, correct) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?)", (category, text, *options, correct))
        return cursor.lastrowid


def get_questions(count=10, category=None):
    """`count` random questions as dicts {id, category, text, options, correct}.
    The four options are shuffled and `correct` points at the right one after shuffling."""
    sql, args = "SELECT * FROM questions", []
    if category:
        sql += " WHERE category = ?"
        args.append(category)
    with connect() as db:
        rows = db.execute(sql, args).fetchall()
    random.shuffle(rows)
    questions = []
    for row in rows[:count]:
        options = [row[f"opt{i}"] for i in range(4)]
        right = options[row["correct"]]
        random.shuffle(options)
        questions.append({"id": row["id"], "category": row["category"], "text": row["text"],
                          "options": options, "correct": options.index(right)})
    return questions


def save_result(player, score, correct, wrong):
    with connect() as db:
        db.execute("INSERT INTO results (player, score, correct, wrong, played_at) VALUES (?, ?, ?, ?, ?)",
                   (player, score, correct, wrong, datetime.now().isoformat(timespec="seconds")))


def get_leaderboard(limit=10):
    """[{player, games, total_score, best_score}] with the highest total score first."""
    with connect() as db:
        rows = db.execute("SELECT player, COUNT(*) AS games, SUM(score) AS total_score, MAX(score) AS best_score "
                          "FROM results GROUP BY LOWER(player) ORDER BY total_score DESC, best_score DESC LIMIT ?",
                          (limit,)).fetchall()
    return [dict(row) for row in rows]
