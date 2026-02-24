import tkinter as tk
from tkinter import messagebox, scrolledtext
 
import socket
import threading

bg_color = "#F3B9DF" # background and foreground colors for the GUI 
fg_color = "black"


class SUquidQuizClient:

    def __init__(self, master: tk.Tk): #constructor
        self.master = master # stores  master ins teh main tkinter window
        self.master.title("SUquid Quiz Client")
        self.master.configure(bg=bg_color)

        self.client_socket = None #tcp socket obj
        self.is_connected = False # connection status flag  to controlthreads
        self.rec_thread = None #bgtread for recieving thread

        self.answer_var = tk.StringVar(value="") # tkinter variable to hold selected answer from radio buttons

        self.create_widgets()
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing) # handle window close event, so socket closes

    #### GUI Setup and Layout

    def create_widgets(self):
        # connection frame that holds IP, Port, Username entries for player to connect to server
        conn_frame = tk.Frame(self.master, bg=bg_color)
        conn_frame.grid(row=0, column=0, columnspan=6, padx=10, pady=5, sticky="w")

        tk.Label(conn_frame, text="IP:", bg=bg_color, fg=fg_color).grid(row=0, column=0)
        self.ip_entry = tk.Entry(conn_frame)
        self.ip_entry.grid(row=0, column=1)

        tk.Label(conn_frame, text="Port:", bg=bg_color, fg=fg_color).grid(row=0, column=2)
        self.port_entry = tk.Entry(conn_frame)
        self.port_entry.grid(row=0, column=3)

        tk.Label(conn_frame, text="Username:", bg=bg_color, fg=fg_color).grid(row=0, column=4)
        self.username_entry = tk.Entry(conn_frame)
        self.username_entry.grid(row=0, column=5)

        self.connect_button = tk.Button(self.master, text="Connect", command=self.toggle_connection)
        self.connect_button.grid(row=1, column=0, columnspan=6, pady=5)

        radio_frame = tk.Frame(self.master, bg=bg_color)
        radio_frame.grid(row=2, column=0, columnspan=6)

        tk.Radiobutton(radio_frame, text="A", value="A", variable=self.answer_var, # all buttons share same variable so one answeer is selected
                       bg=bg_color, fg=fg_color).grid(row=0, column=1)
        tk.Radiobutton(radio_frame, text="B", value="B", variable=self.answer_var,
                       bg=bg_color, fg=fg_color).grid(row=1, column=1)
        tk.Radiobutton(radio_frame, text="C", value="C", variable=self.answer_var,
                       bg=bg_color, fg=fg_color).grid(row=2, column=1)

        self.submit_button = tk.Button(self.master, text="Submit",
                                       command=self.submit_answer, state=tk.DISABLED) #disabled until recieve question, prevents invalid submission
        self.submit_button.grid(row=3, column=0, columnspan=6, pady=5)

        # message display frame containing a scrollable listbox 
        frame = tk.Frame(self.master, bg=bg_color)
        frame.grid(row=4, column=0, columnspan=6, padx=10, pady=10, sticky="nsew")

        self.msg_listbox = tk.Listbox(frame, height=20, width=120,bg=bg_color, fg=fg_color)
        self.msg_listbox.pack(side=tk.LEFT, fill=tk.BOTH)

        scrollbar = tk.Scrollbar(frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.msg_listbox.config(yscrollcommand=scrollbar.set)
        scrollbar.config(command=self.msg_listbox.yview)

    #### Connection Management

    # connect or disconnect based on current state
    def toggle_connection(self): 
        if self.is_connected:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        # get IP, Port, and Username from user entries and remove leading or trailing spaces
        ip = self.ip_entry.get().strip() 
        port = self.port_entry.get().strip()
        username = self.username_entry.get().strip()

        if not ip or not port or not username: # check all fields are filled
            messagebox.showerror("Error", "All fields are required.")
            self.insert_msg_to_listbox("Please fill all fields")
            return

        try:
            port = int(port)
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # creates TCP socket 
            self.client_socket.connect((ip, port))
            self.client_socket.sendall(username.encode())

        except (socket.error, ValueError) as e:
            messagebox.showerror("Connection Failed", str(e))
            self.insert_msg_to_listbox(f"Could not connect: {e}")
            return

        self.is_connected = True
        self.connect_button.config(text="Disconnect")
        self.insert_msg_to_listbox(f"Connected to {ip}:{port} as {username}")

        self.rec_thread = threading.Thread(target=self.receive_messages, daemon=True)
        self.rec_thread.start() #creates bg thread to handle incoming messages  and prevent freezing GUI
        #daemon automatically terminates thread when main program exits

    def disconnect(self):
        if self.is_connected:
            self.is_connected = False # stops recieving loop
            self.client_socket.close()
            self.submit_button.config(state=tk.DISABLED)
            self.connect_button.config(text="Connect")  #restores UI to intial state
            self.insert_msg_to_listbox("Disconnected from server")

    #### Receiving and Processing Messages

    def receive_messages(self):
        while self.is_connected: # loop to continuously receive messages from server as long as conneceted
            try:
                message = self.client_socket.recv(4096) #reads up to 4096 bytes from socket
                if not message:  # server has closed the connection
                    self.master.after(0, self.disconnect)
                    break

                msg = message.decode(errors="ignore")
                self.master.after(0, self.process_server_messages, msg)

            except (socket.error, OSError): #catches network failure, client unplugged from wifi, server crashes
                self.master.after(0, self.disconnect)
                break

    def process_server_messages(self, msg): #euns on main thread to safely update GUI
        if not msg.strip(): # ignore empty messages
            return

        for line in msg.split("\n"): # display the server message line by line for clean structure
            self.insert_msg_to_listbox(line)

        if "Question" in msg: #enable answer submission when question is received
            self.answer_var.set("")
            self.submit_button.config(state=tk.NORMAL)
            self.insert_msg_to_listbox("Select an option and submit to answer the question")

    #### Sending Answers to Server

    def submit_answer(self):
        answer = self.answer_var.get()

        # if no answer selected return with warning
        if not answer: 
            messagebox.showwarning("Warning", "Select an answer first.")
            self.insert_msg_to_listbox("Must select an answer before submitting")
            return

        try:
            self.client_socket.sendall(answer.encode())
            self.submit_button.config(state=tk.DISABLED) # disable submit button until next question, prevents double submissions
            self.insert_msg_to_listbox(f"Your answer '{answer}' was submitted")
        except:
            self.disconnect()

    #### diaplay in listbox
    def insert_msg_to_listbox(self, msg):
        self.msg_listbox.insert(tk.END, msg)
        self.msg_listbox.yview(tk.END)

    def on_closing(self):# handle window close event
        if self.is_connected:
            self.disconnect()
        self.master.destroy()


if __name__ == "__main__": #entry point, enusres GUI runs on main thread
    root = tk.Tk()
    SUquidQuizClient(root)
    root.mainloop()
 #creates main window and starts tkinter event loop
