# DSA Quiz Battle

A desktop quiz game for learning **Data Structures and Algorithms**. Play alone or challenge a friend: answer questions, beat the timer and collect cheers like *Wow!*, *Amazing!* and *Bravo!*.

Built with **Python + Tkinter + SQLite**. Only the standard library is used, nothing to install.

![Welcome](screenshots/welcome.png)

| Quiz | Cheers | Results |
| --- | --- | --- |
| ![Quiz](screenshots/quiz.png) | ![Cheer](screenshots/cheer.png) | ![Results](screenshots/results.png) |

## Download and play (Windows)
Go to the **Releases** page of this repository and download `DSAQuizBattle.exe`. Double-click it, no Python needed.

## Run from source
```
python main.py
```
Needs Python 3.8+. The database `quiz_battle.db` and 26 starter questions are created on the first run.

## Features
- 1 Player or 2 Players mode
- Dark purple pro design: glowing card, gradient buttons, 3D "?" decor
- Cheers for correct answers, streak bonuses (Double!, Hat-trick!, Unstoppable!) and "Lightning fast!"
- Two players sit at their computers; the turn slides to the active player
- 3-2-1-GO countdown, 15 s timer ring, 50:50 lifeline, Pause, Review of previous questions
- Results with trophy, confetti, accuracy and best streak
- Questions and results stored in SQLite, with a leaderboard function

**Keys:** 1-4 / A-D answer, Enter next, H 50:50, R review, P pause, M sound, F11 fullscreen.

## Data structures (in `game.py`)
| Structure | Used for |
| --- | --- |
| List | questions and their 4 options |
| Queue (`deque`) | order of the questions (FIFO) |
| Dictionary | scores, correct and wrong counts per player |
| Stack | answered questions, for Review (LIFO) |

## Project files
| File | Purpose |
| --- | --- |
| `main.py` | starts the game, connects GUI, logic and database |
| `gui.py`, `ui_kit.py` | screens, drawing tools, animations, sound |
| `game.py` | game logic (no tkinter, easy to test) |
| `database.py` | SQLite questions and results |
| `test_game.py`, `test_database.py` | automatic tests (`python test_game.py`) |
| `build_exe.bat` | builds `DSAQuizBattle.exe` on Windows |

## Build the .exe yourself (Windows)
Install Python, then double-click `build_exe.bat`. The game is created in `dist\DSAQuizBattle.exe`.

## Team
Nisha, Vanshika, Kajal, Ravina
