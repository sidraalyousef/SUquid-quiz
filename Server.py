import tkinter as tk
from tkinter import scrolledtext, messagebox
import socket
import threading
import select
from queue import Queue, Empty


class GameServer:
    # constructor:
    def __init__(self, master:tk.Tk):
        self.master = master
        master.geometry("700x500")
        master.title("Game Server")

        self.server_socket = None
        self.is_listening = False
        self.players = {}  # {client_socket: name}
        self.thread = None
        self.scores = {}  # {username: score}
        self.all_time_scores = {} #stores all scores recorded during the game
        self.questions = []

        self.n_questions = 0 # questions in game
        self.questions_in_file = 0 # questions in the file

        self.round_answers = {} # {client_socket: selected_option}

        self.file_loaded = False
        self.n_questions_valid = False
        self.game_ended = False

        self.inbox = Queue()          # (client_socket, message)
        self.disconnected = set()     # sockets that disconnected

        self.accepting_clients =    False

        self.create_widgets()
        self.master.after(100, self.poll_inbox)

#===================================================================================================================================
# GUI FUNCTIONS:///////////////////////////////////////////////////////////////////////////////////////////////////////////////////
#===================================================================================================================================

    # this function handles the GUI (at the start)
    def create_widgets(self):
        # creating a frame within master for port & listen button
        self.port_frame = tk.Frame(self.master)
        self.port_frame.pack(pady = 20)

        # get port and assign it to attribute so we can access it later
        tk.Label(self.port_frame, text= "Port: ").pack()
        self.port_entry = tk.Entry(self.port_frame)
        self.port_entry.pack()
        
        # creating a button for listening:
        self.listen_button = tk.Button(self.port_frame, text = "Listen", command = self.toggle_listening)
        self.listen_button.pack(pady = 10)



        # log:
        self.log = tk.Listbox(self.master , height = 30,  state = tk.DISABLED, fg = "black", bg = "white")
        self.log.pack(side = tk.LEFT, fill = tk.BOTH, expand = True)

        # scrollbar for the listbox
        scrollbar = tk.Scrollbar(self.master, command=self.log.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log.config(yscrollcommand=scrollbar.set)

        # game setup state: (disabled for now)
        self.game_setup_frame = tk.Frame(self.master)
        # self.game_setup_frame.pack(pady = 30)

        tk.Label(self.game_setup_frame, text = "Enter File Name: ", state = tk.DISABLED).pack()
        self.filename_entry = tk.Entry(self.game_setup_frame, state = tk.DISABLED)
        self.filename_entry.pack()
        
        tk.Label(self.game_setup_frame, text = "Number of Questions: ", state = tk.DISABLED).pack()
        self.n_questions_entry = tk.Entry(self.game_setup_frame, state = tk.DISABLED)
        self.n_questions_entry.pack(pady = 20)

        self.game_start_button = tk.Button(self.game_setup_frame, text = "START GAME", command = self.game_setup, state = tk.DISABLED)
        self.game_start_button.pack(pady = 20)

        self.game_log = tk.Text(self.master, state = tk.DISABLED)

#=================================================================================================================================
# STRTING & STOPPING SERVER: ////////////////////////////////////////////////////////////////////////////////////////////////////
#=================================================================================================================================
    # so we can listen and stop the server from the same button
    # when the server isnt listening: press to listen, if its already listening:  press to stop listening
    def toggle_listening(self):
        if self.is_listening:
            self.stop_listening()
        else:
            self.start_listening()

    # in this function the server socket is created and it starts listening for new clients
    def start_listening(self):
        port_str = self.port_entry.get()

        if not port_str:
            messagebox.showerror("Error", "Please enter a port number.")
            return
        
        try:
            port = int(port_str)
            ip = socket.gethostbyname(socket.gethostname()) # get my ip
            #self.log_message(ip)
            addr = ("0.0.0.0", port)

            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.bind(addr)
            self.server_socket.listen(5)
            
            self.is_listening = True
            self.accepting_clients = True
            self.listen_button.config(text="Stop Listening") # change the text on listen_button
            self.log_message(f"======== SERVER LISTENING ON PORT {(ip, port)} =========")
            #self.log_message(f"Bound addr: {self.server_socket.getsockname()}")
            
            self.thread = threading.Thread(target=self.accept_connections, daemon=True)
            self.thread.start()
            
            self.master.protocol("WM_DELETE_WINDOW", self.on_closing)

        except (socket.error, ValueError) as e:
            messagebox.showerror("Server Error", f"Could not start server: {e}")
            self.is_listening = False
            if self.server_socket:
                self.server_socket.close()

        # function to stop the server and disconnect all clients

    
    # SO THE SERVER STOPS LISTENING: 
    def stop_listening(self): 
        if self.is_listening:
            self.is_listening = False
            self.accepting_clients  = False
            for client_socket in list(self.players.keys()):
                self.remove_client(client_socket)
            
            self.server_socket.close()
            self.listen_button.config(text="Listen") # change listen_button text back to listen
            self.log_message("--- Server stopped ---")

    # when window is closed: do this:
    def on_closing(self):
        if self.is_listening:
            self.stop_listening()
            self.broadcast("Server disconnected")
        self.master.destroy()
#===================================================================================================================================
# HANDLING CONNECTIONS: ///////////////////////////////////////////////////////////////////////////////////////////////////////////
#===================================================================================================================================
    def accept_connections(self):
        #while self.is_listening and self.accepting_clients:
        while True:
            try:
                client_socket, client_address = self.server_socket.accept()
                client_socket.settimeout(1.0)
                username = client_socket.recv(1024).decode()

                if not self.accepting_clients:
                    client_socket.sendall("game ongoing u cant join".encode())
                    self.log_message("new client tried to connect during game, connection wasnt accepted")
                    client_socket.close()
                    continue  # maybe shouold change to continue?
                
                # basic validation
                if not username:
                    client_socket.send("ERROR: Username required".encode())
                    client_socket.close()
                    continue

                # reject if username already connected
                if username in self.players.values():
                    self.log_message(f"Player with username '{username}' tried to connect but there is already a player with that username")
                    client_socket.send(f"ERROR: Username '{username}' already connected".encode())
                    client_socket.close()
                    continue

                #after validating new client connections
                self.players[client_socket] = username
                self.log_message(f"New connection from {client_address[0]} as '{username}'")
                self.broadcast(f"player {username} joined the game")


                # thread for each client
                client_thread = threading.Thread(target=self.handle_client, args=(client_socket, username), daemon=True)
                client_thread.start()

                self.players[client_socket] = username

                if len(self.players.keys()) >= 1:
                    self.start_game_setup()

            except (socket.error, OSError):
                break
    
#=================================================================================================================================
# HANDLING MESSAGES + DICONNNECTIONS IN INBOX: ///////////////////////////////////////////////////////////////////////////////////
#================================================================================================================================   
    # function to MONITOR CLIENT MESSAGES, add them to queue
    def handle_client(self, client_socket, username):
        try:
            client_socket.sendall(f"Welcome {username}! *-*".encode("utf-8"))

            while not self.game_ended:
                try:
                    data = client_socket.recv(1024)
                    if not data:
                        self.inbox.put((client_socket, None))
                        break

                    msg = data.decode("utf-8", errors="ignore").strip()
                    if msg:
                        self.inbox.put((client_socket, msg))

                except socket.timeout:
                    # no data yet
                    continue

        except (OSError, socket.error):
            self.inbox.put((client_socket, None))

    # function to processes messages in queue
    def poll_inbox(self):
        #Continuously process messages/disconnects from client threads
        drained = 0
        while True:
            try:
                s, msg = self.inbox.get_nowait()
            except Empty:
                break

            drained += 1

            # disconnect event
            if msg is None:
                if s in self.players:
                    self.remove_client(s, reason="disconnected")
                continue


        # keep polling forever
        self.master.after(100, self.poll_inbox)

    #fucntion to eemove the client from dicts and notify server and players
    def remove_client(self, client_socket, reason="got disconnected"):
        username = self.players.get(client_socket, None)

        # remove from dicts first
        if client_socket in self.players:
            del self.players[client_socket]

        if username in self.scores:
            del self.scores[username]

        # close socket
        try:
            client_socket.close()
        except:
            pass

        # announce
        if username:
            self.log_message(f"'{username}' left the game ({reason}).")
            self.broadcast(f"player '{username}' left the game ({reason}).")

        if not self.game_ended:
            if len(self.players) >= 2:
                self.game_start_button.config(state=tk.NORMAL)
            else:
                self.game_start_button.config(state=tk.DISABLED)

#===================================================================================================================================
# LOG FUNCTIONS: ////////////////////////////////////////////////////////////////////////////////////////////////////////////
#===================================================================================================================================
    
    def log_message(self, message):
        if isinstance(message, list):
            for line in message:
                self.log_message(line)
            return

        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, message + "\n")
        self.log.config(state=tk.DISABLED)
        self.log.yview(tk.END)

    def clear_log(self):
        self.log.config(state=tk.NORMAL)
        self.log.delete(0, tk.END)
        self.log.config(state=tk.DISABLED)
#===================================================================================================================================
# GAME SETUP WINDOW: filename, n_questions/////////////////////////////////////////////////////////////////////////////////////////
#===================================================================================================================================
    # the window shows after we have 1, connction but the ebutton only works after theres 2 or more connections
    def start_game_setup(self):
        self.port_entry.config(state = tk.DISABLED)
        self.listen_button.config(state = tk.DISABLED)
        self.port_frame.pack_forget()

        self.game_setup_frame.pack(pady = 30)
        self.filename_entry.config(state = tk.NORMAL)
        self.n_questions_entry.config(state = tk.NORMAL)

        if len(list(self.players.keys())) >=2 :
            self.game_start_button.config(state = tk.NORMAL)


    def game_setup(self):
        self.file_loaded = False
        self.n_questions_valid = False

        self.questions = []
        self.questions_in_file = 0
        self.all_time_scores = {}

        #file handling
        filename = self.filename_entry.get().strip()

        if not filename:
            messagebox.showerror("ERROR", "PLEASE ENTER FILE NAME")
            return

        try:
            with open(filename, "r", encoding = "utf-8") as file:
                lines = [line.strip() for line in file.readlines()]

                self.quiz = lines

                self.file_loaded = True
                self.log_message(f"file {filename} opened successfully")
                self.questions_in_file = int(len(lines) / 5)
                self.log_message(f"number of questions in file: {self.questions_in_file}")

                """
                # filling correct_answers dict: (assumes file is correctly formatted, no invalid options)
                question_number = 1
                for i in range(0, len(lines), 5): # start 0 ==> len(lines), jump 5 indices at a time
                    correct_option = lines[i + 4][-1].upper() 
                    self.correct_answers[question_number] = correct_option
                    question_number += 1
                    """
                
                # filling self.questions list
                for i in range(0, len(lines), 5):
                    q_text = lines[i]
                    options = [lines[i+1], lines[i+2], lines[i+3]]   # A, B, C and text
                    correct = lines[i+4].strip()[-1].upper()             # correct option
                    self.questions.append({"question": q_text, "options": options, "correct_option": correct})

                file.close()

        except FileNotFoundError:
            messagebox.showerror("ERROR", "FILE NOT FOUND")
        except PermissionError:
            messagebox.showerror("File Error", f"No permission to read '{filename}'.")
        except Exception as e:
            messagebox.showerror("File Error", str(e))

        # number of questions handling
        n_q = self.n_questions_entry.get().strip()

        try:
            self.n_questions = int(n_q)
            self.n_questions_valid = True
            self.log_message(f"number of questions in game: {self.n_questions}")
        
        except ValueError:
            messagebox.showerror("Input error", "number of questions should be an integer")
            return
        
        # more validation of n_q
        if self.n_questions <= 0:
            messagebox.showerror("Input error", "Number of questions must be > 0")
            return
        
        # if the number is too big that it makes no sense
        if self.n_questions > 100:
            messagebox.showerror("Input error", "Number of question siis too big pls be reasonable -_-")
            return
        
        
        # now start game when everything good:
        #self.is_listening = False
        if self.file_loaded and self.n_questions_valid:
            threading.Thread(target=self.start_game, daemon=True).start()
        #self.start_game()

#==================================================================================================================================
# GAME FLOW DISPLAY HELPERS: broadcast, display scoreboard, display question, dislay rankings /////////////////////////////////////////////////////
#==================================================================================================================================
    # function  to send message to all players
    def broadcast(self, message, sender_socket=None):
        if isinstance(message, list):
            for line in message:
                self.broadcast(str(line)+"\n")
            return

        for client_socket in list(self.players.keys()):
            try:
                client_socket.sendall(message.encode("utf-8"))
            except (socket.error, OSError):
                self.remove_client(client_socket)

#=================================================================================================================================
    """
    def scoreboard(self, scores):
        self.log_message("\n===== SCOREBOARD =====")

        if not scores:
            self.log_message("No scores to display.")
            return

        for username, score in scores.items():
            self.log_message(f"{username:<15} : {score}")

        self.log_message("======================") """
    
    # function to display screboard
    def scoreboard(self, scores):
        lines = []
        lines.append("===== SCOREBOARD =====")

        if not scores:
            lines.append("No scores to display.")
            lines.append("======================")
            return lines

        for username, score in scores.items():
            lines.append(f"{username:<15} : {score}")

        lines.append("======================")

        return lines
#=================================================================================================================================
    #function to display question
    def display_question(self, file_q_index, n_q_game):
        q = self.questions[file_q_index]
        lines = []

        lines.append("[QUESTION]")
        lines.append("" + "=" * len(q["question"]))
        lines.append(f"Question {n_q_game}")
        lines.append("" + q["question"])
        lines.append("" +q["options"][0])  # OPTION A
        lines.append("" +q["options"][1])  #  OPTION B
        lines.append("" +q["options"][2])  # OPTION C
        lines.append("=" * len(q["question"]) + "\n")

        return lines

    # function to display results and rankings at the end of the game
    def display_results(self, scores):
        # scores: {username: points}

        # 1) sort by score desc, then name asc (for stable display)
        sorted_items = sorted(scores.items(), key=lambda x: (-x[1], x[0]))

        lines = []
        lines.append("===== GAME OVER =====")
        lines.append("=== FINAL RESULTS ===")

        prev_score = None
        rank = 0  # will be set when we see first item

        for idx, (username, pts) in enumerate(sorted_items):
            # idx is 0-based position in the sorted list
            if pts != prev_score:
                rank = idx + 1   # competition ranking jump
                prev_score = pts

            lines.append(f"{rank}. {username} — {pts}")

        return lines   
#==================================================================================================================================
# GAME LOGIC FUNCTIONS: ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
#=================================================================================================================================
    def recieve_round_answers(self):
        self.round_answers = {}

        #update list each round
        expected = list(self.players.keys())

        while len(self.round_answers) < len(expected):
            # if too few players, stop the round
            if len(expected) == 0:
                return

            try:
                s, msg = self.inbox.get(timeout=1.0)
            except Empty:
                continue

            # if someone disconnected, remove player and update expected list
            if msg is None:
                if s in self.players:
                    self.remove_client(s, reason="disconnected")
                if s in expected:
                    expected.remove(s)
                continue

            # ignore messages from sockets no longer in game
            if s not in self.players:
                continue

            # ignore if already answered
            if s in self.round_answers:
                continue

            letter = msg[0].upper()
            self.round_answers[s] = letter


#===================================================================================================================================
    def grade_round(self, n_file_q, round_answers):
        correct_option = self.questions[n_file_q]["correct_option"]
        
        first_correct = None
        additional_points = len(self.players) - 1

        for s, selected_option in self.round_answers.items():
            username = self.players.get(s)  # use .get() instead of direct access
            if username is None:
                continue  # player already disconnected, skip them entirely

            added_points = 0

            if selected_option == correct_option:
                self.scores[username] += 1
                self.all_time_scores[username] += 1
                added_points += 1

                if first_correct is None:
                    first_correct = username
                    self.scores[username] += additional_points
                    self.all_time_scores[username] += additional_points
                    added_points += additional_points

                try:
                    if username == first_correct:
                        s.sendall(f"You were the first to answer correctly! You got {added_points} points!".encode("utf-8"))
                    else:
                        s.sendall(f"Correct Answer! You got {added_points} point!".encode("utf-8"))
                except (socket.error, OSError):
                    pass  # player disconnected between answering and feedback, ignore

            else:
                try:
                    s.sendall(f"Your Answer is wrong, the correct answer is {correct_option}".encode("utf-8"))
                except (socket.error, OSError):
                    pass  # same, ignore closed sockets
                    s.sendall(f"Your Answer is wrong, the correct answer is {correct_option}".encode("utf-8"))

#===================================================================================================================================
    def end_game(self):
        self.broadcast("Game ended. Bye Bye")
        for s in list(self.players.keys()):
            self.remove_client(s, "was removed")
        self.game_started = False
        self.game_ended = False
        self.is_listening = True
        self.accepting_clients = True
        self.log_message("a new game can be started if u want")

#==================================================================================================================================
    def start_game(self):
            
        try:
            #self.clear_log()
            self.game_setup_frame.pack_forget()
            self.game_started = True
            self.is_listening = False
            self.accepting_clients = False
            self.log_message("===== STARTING GAME! =====")
            self.log_message(f"Players: {list(self.players.values())}")
            self.log_message(f"Questions to use: {self.n_questions}")

            #initialize players scores to 0
            for username in self.players.values():
                self.scores[username] = 0
                self.all_time_scores[username] = 0


            for line in self.scoreboard(self.scores):
                self.log_message(line)

            self.broadcast(self.scoreboard(self.scores))

            
            for i in range(1, self.n_questions +1): # questions in game
                n_file_q = ((i - 1)) % self.questions_in_file

                self.broadcast(self.display_question(n_file_q, i))


                # here recieve answers from cients and add them to round_answers dictionary
                self.recieve_round_answers()

                # grade round and siplay updated scoreboard when all answers are recieved
                if len(self.round_answers.keys()) == len(self.players.keys()) and len(self.round_answers) > 0:
                    #self.clear_log()
                    self.grade_round(n_file_q, self.round_answers) # the scores should be updated in this function
                    
                    self.log_message(f"question {i} asked, scores so far:")
                    for line in self.scoreboard(self.scores):
                        self.log_message(line)
                    self.broadcast(self.scoreboard(self.scores))
                
                # need to clear round answers before moving on to next question- happens in recieve scores

                # if we are in the  last q display results:
                if i == self.n_questions or len(self.players.keys()) < 1:
                    result_text = self.display_results(self.all_time_scores)

                    for line in result_text:
                        self.log_message(line)

                    self.broadcast(result_text)
                    break
            self.game_ended = True
            if self.game_ended:
                self.end_game()
    

        except Exception as e:  # for log issues
            self.log_message(f"ERROR in game: {e}")  

#===================================================================================================================================
if __name__ == "__main__":
    root = tk.Tk()
    app = GameServer(root)
    root.mainloop()
