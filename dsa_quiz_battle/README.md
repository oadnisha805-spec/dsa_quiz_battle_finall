# DSA Quiz Battle (Tkinter frontend)

Run: `python main.py`  (Python 3.8+, only the standard library, Windows/Mac/Linux; sound beeps on Windows only)

## Features
- Dark purple pro design: glowing card, gradient pill options, 3D "?" decor, purple accent headlines
- Cheers after a correct answer: Wow! Amazing! Bravo! Brilliant! Superb! Genius! ... plus Lightning fast!, Double!, Hat-trick!, Unstoppable!
- Two players seated at their computers (left and right); the turn pill slides to the active player, the other one dims. Players smile+bounce with a speech bubble on a correct answer and frown on a wrong one
- Streak counter, floating +points, star bursts, confetti for the winner, score count-up
- 3-2-1-GO countdown, 15 s timer ring, 50:50 lifeline, Pause, Review (stack, newest first)
- Play alone (1 Player) or with a friend (2 Players); solo gets its own results card
- Keys: 1-4 / A-D answer, Enter next, H 50:50, R review, P pause, M sound, F11 fullscreen

## Files
- gui.py (screens), ui_kit.py (drawing tools), game.py (logic: deque, stack, dicts), fake_game.py (sample questions), main.py, test_game.py

## Database (SQLite)
- `database.py` creates `quiz_battle.db` on the first run with 26 DSA questions (Stack, Queue, Complexity, Hashing, Array, Linked List, Tree, Graph, Sorting, Recursion).
- `get_questions(n)` gives random questions with shuffled options; `save_result(...)` stores each player's score; `get_leaderboard()` ranks players.
- Add your own: `database.add_question(category, text, [4 options], correct_index)`.
- Tests: `python test_game.py` and `python test_database.py`
