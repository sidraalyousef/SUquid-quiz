# 🦑 SUquid Quiz
A real-time multiplayer trivia quiz game built with Python. Players connect over TCP sockets to compete in live quiz rounds with dynamic scoring — first correct answer gets bonus points. Features a tkinter GUI for both server and client, multithreaded connection handling, and graceful mid-game disconnection support

**Authors:** Sedra Alyousef (server) & Salma Tubail (client)

---
## Features

- Multiple players can join and compete simultaneously
- Real-time scoring — the first player to answer correctly gets bonus points
- Scoreboard displayed after every round
- Full final rankings when the game ends, including players who disconnected mid-game
- Players who drop out mid-round don't crash or freeze the game for everyone else
- Server GUI for easy setup and live game monitoring
- Client GUI with radio buttons for answer selection

---

## Requirements

- Python 3.x
- No external libraries needed — only Python's standard library (`tkinter`, `socket`, `threading`, `queue`)

---

## How to Run

**1. Start the server**
```
python 33520_Alyousef_Sedra_Server.py
```
- Enter a port number (e.g. `5000`) and click **Listen**
- Once players connect, enter the question file name and number of questions, then click **START GAME**
- The START GAME button becomes active once at least 2 players have joined

**2. Start the client(s)**
```
python 33749_Salma_Tubail_client.py
```
- Enter the server's IP address, port, and a username, then click **Connect**
- Run this on as many machines (or terminals) as you have players

**3. Question file format**

The question file must be a plain `.txt` file where every question takes exactly 5 lines:

```
What is the capital of France?
A) London
B) Paris
C) Berlin
correct: B
```

- Line 1: the question text
- Lines 2–4: the three options (A, B, C)
- Line 5: the correct answer — the last character on this line is read as the answer letter (e.g. `B`)

Repeat this 5-line block for every question in the file, with no blank lines between them.

---

## How the Protocol Works

Communication between server and clients is done over **TCP sockets**. Here is the flow:

1. **Handshake** — when a client connects, the first thing it sends is its username. The server validates it (non-empty, not a duplicate) and either accepts or rejects the connection.

2. **Welcome message** — on acceptance, the server sends a welcome message back to the client via its dedicated thread.

3. **Game messages** — the server broadcasts questions, scoreboards, and result screens to all connected clients as formatted text strings.

4. **Answer collection** — clients send a single letter (`A`, `B`, or `C`) when they submit an answer. The server collects answers from all players into a queue before grading the round.

5. **Thread-safe inbox** — each client has its own receiving thread that puts incoming messages into a shared `Queue`. The main thread drains this queue every 100ms using `tkinter`'s `after()` loop, keeping all GUI updates on the main thread and avoiding race conditions.

6. **Disconnection handling** — if a player disconnects mid-round, their socket is removed from the expected list so the round still completes for the remaining players. Their score up to that point is preserved and shown in the final results.

---

## Design Decisions & Challenges

**Thread-safe GUI updates**
tkinter is not thread-safe — updating the GUI from a background thread causes crashes and unpredictable behaviour. To solve this, client receiving threads never touch the GUI directly. Instead they put messages into a `Queue`, and the main thread polls that queue every 100ms using `master.after()`, processing messages and updating the GUI safely.

**Handling disconnections mid-round**
One of the trickier parts of the project. When a player disconnects, we had to decide: do we cancel the round, or let it continue? We chose to let it continue. The server takes a snapshot of expected players at the start of each round, and if someone disconnects, they're removed from that snapshot. The round finishes for whoever remains. This required careful handling to avoid trying to send feedback to a socket that had already been closed.

**Preserving scores after disconnection**
Originally, `remove_client()` deleted the player's score when they left. This meant disconnected players didn't appear in the final results. We introduced a separate `all_time_scores` dictionary that is never deleted from — active scoreboards use `scores` (current players only), while the final results use `all_time_scores` (everyone who ever played).

**Bonus points for speed**
To reward fast answers, the first player to answer correctly in a round gets extra points equal to the number of other players in the game. This means the point gap can grow quickly in larger lobbies, keeping the competition exciting.

---
## Project Structure:

```
├── Server.py                    # Server application
├── Client.py                    # Client application
├── questions.txt                # Example question file
└── README.md
```
