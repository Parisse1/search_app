import tkinter as tk
from tkinter import filedialog, messagebox
import sqlite3
from tkinter import ttk
import os
import threading
import queue
import json

# Dichiarare tree come variabile globale
tree = None
# Variabile per tenere traccia del numero di oggetti nel database
num_items = 0
# Variabile per segnalare l'interruzione del thread
thread_interrupted = False
# Variabile per tenere traccia della scelta dell'utente
scan_files = False
# coda (queue) per gestire le directory da scansionare e i thread:
directory_queue = queue.Queue()

configurations_window = None
configurations_tree = None

bold_font = ("Helvetica", 10, "bold")

# Funzione per mostrare i risultati su una tabella nella stessa finestra
def display_results(results):
    global tree  # Dichiarare tree come variabile globale
    for i in tree.get_children():
        tree.delete(i)

    results.sort()  # Ordina i risultati in ordine alfabetico
    for result in results:
        # Controlla se il risultato è una directory o un file
        is_directory = not os.path.isfile(result)
        if is_directory:
            # Includi il tag "directory" per le directory
            tree.insert("", "end", values=(result,), tags=("directory",))
        else:
            # Lascia vuoto il tag per i file (saranno normali)
            tree.insert("", "end", values=(result,))

# Funzione per gestire il doppio clic su una riga della tabella
def on_tree_double_click(event):
    global tree  # Dichiarare tree come variabile globale
    item = tree.selection()[0]  # Ottieni l'elemento selezionato (riga)
    directory_path = tree.item(item, "values")[0]  # Ottieni il valore della colonna "Directory"
    
    # Controllo se è un file o una directory
    if os.path.isfile(directory_path):
        # Se è un file, apri la directory padre
        directory_path = os.path.dirname(directory_path)
        
    open_directory(directory_path)
    
# Funzione per aprire il percorso in Esplora file (o il gestore di file predefinito)
def open_directory(directory_path):
    try:
        # Utilizza un percorso corretto usando "os.startfile" per aprire il percorso con il gestore di file predefinito
        os.startfile(directory_path)
    except Exception:
        # Gestisci eventuali eccezioni se l'apertura del percorso fallisce
        pass

# Funzione per selezionare una directory e avviare la scansione
def select_directory():
    global thread_interrupted  # Dichiarare la variabile globale thread_interrupted
    global scan_files  # Dichiarare la variabile globale scan_files
    global num_items
    root = tk.Tk()
    root.withdraw()  # Nascondi la finestra principale
    result = messagebox.askquestion("Scansione", "Scansionare anche i file?", icon='question')
    if result == 'yes':
        scan_files = True
    else:
        scan_files = False

    directory_path = filedialog.askdirectory()
    if directory_path:
        thread_interrupted = False  # Reimposta il flag di interruzione
        num_items = 0  # Reimposta il conteggio
        progress_bar["value"] = 0
        progress_bar["maximum"] = 100
        progress_bar.start()
        t = threading.Thread(target=scan_and_save_subdirectories, args=(directory_path, on_scan_complete))
        t.start()

# Funzione per interrompere il thread
def interrupt_thread():
    global thread_interrupted
    thread_interrupted = True

def on_scan_complete():
    global num_items
    progress_bar.stop()
    select_button["state"] = "normal"
    search_button["state"] = "normal"
    clear_database_button["state"] = "normal"
    show_all_button["state"] = "normal"
    status_label.config(text=f"Scansione terminata.")
    update_info_label() 

# Funzione per cercare nel database con parole chiave multiple
def search_directory(event=None):
    search_term = search_entry.get()
    if not search_term:
        # Il campo di ricerca è vuoto, non fare nulla
        return
    conn = sqlite3.connect('directories.db')
    cursor = conn.cursor()

    search_terms = search_term.split('*')
    search_query = ' AND '.join(f"directory LIKE '%{term}%'" for term in search_terms)

    if show_files_var.get():
        # Mostra sia le directory che i file
        query = "SELECT directory FROM directories WHERE " + search_query
    else:
        # Mostra solo le directory (is_file == 0)
        query = "SELECT directory FROM directories WHERE " + search_query + " AND is_file = 0"

    cursor.execute(query)
    results = [result[0] for result in cursor.fetchall()]  # Estrai i risultati correttamente
    display_results(results)
    conn.close()

def clear_database():
    global num_items

    # Chiedi conferma all'utente tramite una finestra di dialogo
    confirmation = messagebox.askquestion("Conferma", "Sei sicuro di voler svuotare il database?", icon='warning')

    if confirmation == 'yes':
        num_items == 0
        conn = sqlite3.connect('directories.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM directories")
        conn.commit()
        conn.close()
        status_label.config(text="Database svuotato")
        update_info_label()
    else:
        # L'utente ha scelto di annullare l'operazione, non fare nulla
        pass

# Funzione per aggiornare la barra di avanzamento
def update_progress(progress):
    progress_bar["value"] = progress

# Funzione per scansionare e salvare tutti i percorsi delle sottocartelle
def scan_and_save_subdirectories(directory, callback):
    global thread_interrupted, num_items  # Dichiarare le variabili globali
    
    select_button["state"] = "disabled"
    search_button["state"] = "disabled"
    clear_database_button["state"] = "disabled"
    show_all_button["state"] = "disabled"
    status_label.config(text=f"Scansione in corso...{directory}")

    # Creazione del database e della tabella se non esistono
    conn = sqlite3.connect('directories.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS directories (directory TEXT, is_file INTEGER)')
    conn.commit()
    
    # Gestione delle eccezioni durante il calcolo di total_files
    try:
        total_files = len([name for name in os.listdir(directory)])
    except Exception as e:
        messagebox.showerror("Errore", f"Errore durante il calcolo di total_files: {str(e)}")
        total_files = 0  # Impostiamo total_files a 0 in caso di errore

    for progress, (root, dirs, files) in enumerate(os.walk(directory)):
        if thread_interrupted:
            conn.close()
            return
        
        
        # All'interno del ciclo, controlla se il percorso (directory o file) esiste già nel database
        for dir_name in dirs:

            dir_path = os.path.join(root, dir_name).replace("\\", "/")  # Sostituisci le barre rovesciate
            cursor.execute("SELECT directory FROM directories WHERE directory = ? AND is_file = 0", (dir_path,))
            existing_dir = cursor.fetchone()
            if not existing_dir:
                cursor.execute("INSERT INTO directories (directory, is_file) VALUES (?, ?)", (dir_path, 0))
                num_items += 1  # Incrementa il conteggio
                status_label.config(text=f"Scansione in corso...{directory}{num_items}")

        if scan_files:
            for file_name in files:
                file_path = os.path.join(root, file_name).replace("\\", "/")
                file_path = file_path.encode('utf-8', 'ignore').decode('utf-8')
                cursor.execute("SELECT directory FROM directories WHERE directory = ? AND is_file = 1", (file_path,))
                existing_file = cursor.fetchone()
                if not existing_file:
                    cursor.execute("INSERT INTO directories (directory, is_file) VALUES (?, ?)", (file_path, 1))
                    num_items += 1
                    status_label.config(text=f"Scansione in corso...{directory}{num_items}")

        update_progress((progress + 1) * 100 / total_files)

    
    conn.commit()
    conn.close()
    callback()  # Notifica la scansione completata

# Funzione per mostrare tutti gli oggetti del database nella tabella
def show_all_items(show_files):
    conn = sqlite3.connect('directories.db')
    cursor = conn.cursor()

    if show_files:
        # Mostra sia le directory che i file
        cursor.execute("SELECT directory FROM directories")
    else:
        # Mostra solo le directory (is_file == 0)
        cursor.execute("SELECT directory FROM directories WHERE is_file = 0")

    results = [result[0] for result in cursor.fetchall()]  # Estrai i risultati correttamente
    display_results(results)
    conn.close()
    
def update_info_label():
    try:
        conn = sqlite3.connect('directories.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM directories")
        count = cursor.fetchone()[0]
        conn.close()
        info_label.config(text=f"Numero di righe nel database: {count}")
    except:
        pass

def scan_directories_from_queue():
    while not directory_queue.empty():
        directory = directory_queue.get()
        t = threading.Thread(target=scan_and_save_subdirectories, args=(directory, on_scan_complete))
        t.start()
        t.join()  # Attendere la fine del thread prima di continuare con il successivo
        
# Funzione per avviare le scansioni automatiche
def start_auto_scan():
    global num_items
    num_items == 0
    global scan_files  # Dichiarare la variabile globale scan_files
    root = tk.Tk()
    root.withdraw()  # Nascondi la finestra principale
    result = messagebox.askquestion("Scansione", "Scansionare anche i file?", icon='question')
    if result == 'yes':
        scan_files = True
    else:
        scan_files = False
    auto_scan_button["state"] = "disabled"  # Disabilita il pulsante durante le scansioni

    with open("autoscan_conf.json", "r") as json_file:
        data = json.load(json_file)
        for entry in data:
            directory_queue.put(entry["directory"])

    # Avvia un thread principale per gestire le scansioni
    main_thread = threading.Thread(target=main_auto_scan)
    main_thread.start()

# Funzione principale per gestire le scansioni
def main_auto_scan():
    global num_items
    num_items == 0
    while not directory_queue.empty():
        directory = directory_queue.get()
        t = threading.Thread(target=scan_and_save_subdirectories, args=(directory, on_scan_complete))
        t.start()
        t.join()  # Attendere che il thread di scansione termini prima di continuare

    # Alla fine delle scansioni, riabilita il pulsante
    auto_scan_button["state"] = "normal"

def show_context_menu(event):
    if tree.identify_row(event.y):
        context_menu.post(event.x_root, event.y_root)

def delete_selected_item():
    selected_items = tree.selection()
    if selected_items:
        item = selected_items[0]
        directory = tree.item(item, "values")[0]
        conn = sqlite3.connect('directories.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM directories WHERE directory=?", (directory,))
        conn.commit()
        conn.close()
        tree.delete(item)
        update_info_label()
    else:
        messagebox.showwarning("Nessuna riga selezionata", "Seleziona una riga prima di eliminare.")

# Funzione per aprire la finestra delle configurazioni
def open_configurations_window():
    global configurations_window, configurations_tree

    if configurations_window is not None:
        # La finestra è già aperta, non è necessario aprirla di nuovo
        return

    configurations_window = tk.Toplevel(root)
    configurations_window.title("Configurazioni dei Percorsi")

    # Crea una tabella per visualizzare le configurazioni
    configurations_tree = ttk.Treeview(configurations_window, columns=("Directory"))
    configurations_tree.column("#0", width=0, stretch=tk.NO)
    configurations_tree.column("#1", width=1000, anchor="w")
    configurations_tree.heading("#1", text="Directory")

    # Leggi le configurazioni dal file JSON e inseriscile nella tabella
    with open("autoscan_conf.json", "r") as json_file:
        data = json.load(json_file)
        for entry in data:
            directory = entry["directory"]
            configurations_tree.insert("", "end", values=(directory, "Elimina"))

    # Abilita le barre di scorrimento verticale
    configurations_scrollbar = ttk.Scrollbar(configurations_window, orient="vertical", command=configurations_tree.yview)
    configurations_tree.configure(yscrollcommand=configurations_scrollbar.set)
    configurations_scrollbar.pack(side="right", fill="y")


    # Aggiungi la tabella alla finestra
    configurations_tree.pack(fill="both", expand=True)

    # Associa la funzione `open_directory` al doppio clic su una riga della tabella
    configurations_tree.bind("<Double-1>", open_directory)

    # Gestisci la chiusura della finestra
    configurations_window.protocol("WM_DELETE_WINDOW", close_configurations_window)
    
        # Aggiungi il pulsante "Aggiungi"
    add_button = tk.Button(configurations_window, text="Aggiungi", command=add_configuration)
    add_button.pack(side="left", padx=5, pady=5)

    # Aggiungi il pulsante "Elimina"
    delete_button = tk.Button(configurations_window, text="Elimina", command=delete_configuration)
    delete_button.pack(side="left", padx=5, pady=5)



# Funzione per eliminare una configurazione selezionata
def delete_configuration():
    selected_item = configurations_tree.selection()
    if selected_item:
        item = configurations_tree.item(selected_item, "values")
        directory_to_delete = item[0]

        # Leggi le configurazioni dal file JSON
        with open("autoscan_conf.json", "r") as json_file:
            data = json.load(json_file)

        # Rimuovi la configurazione selezionata
        updated_data = [entry for entry in data if entry["directory"] != directory_to_delete]

        # Scrivi le modifiche nel file JSON
        with open("autoscan_conf.json", "w") as json_file:
            json.dump(updated_data, json_file, indent=4)

        # Aggiorna la tabella
        load_configurations()

# Funzione per caricare le configurazioni dalla tabella
def load_configurations():
    # Svuota la tabella
    for item in configurations_tree.get_children():
        configurations_tree.delete(item)

    # Leggi le configurazioni dal file JSON
    with open("autoscan_conf.json", "r") as json_file:
        data = json.load(json_file)

    # Aggiungi le configurazioni alla tabella
    for entry in data:
        directory = entry["directory"]
        configurations_tree.insert("", "end", values=(directory, "Elimina"))

def close_configurations_window():
    global configurations_window, configurations_tree
    configurations_window.destroy()
    configurations_window = None
    configurations_tree = None
    
def add_configuration():
    # Crea una finestra modale per l'aggiunta di una nuova configurazione
    add_window = tk.Toplevel(configurations_window)
    add_window.title("Aggiungi Configurazione")

    new_directory_label = tk.Label(add_window, text="Nuova Directory:")
    new_directory_label.pack()

    new_directory_entry = tk.Entry(add_window)
    new_directory_entry.pack()

    save_button = tk.Button(add_window, text="Salva", command=lambda: save_new_configuration(add_window, new_directory_entry.get()))
    save_button.pack()


def save_new_configuration(add_window, new_directory):
    # Aggiungi la nuova configurazione alla tabella e al file JSON
    configurations_tree.insert("", "end", values=(new_directory,))
    add_to_json(new_directory)
    add_window.destroy()


def add_to_json(new_directory):
    # Leggi il file JSON esistente
    with open("autoscan_conf.json", "r") as json_file:
        data = json.load(json_file)

    # Aggiungi la nuova configurazione
    data.append({"directory": new_directory})

    # Scrivi i dati aggiornati nel file JSON
    with open("autoscan_conf.json", "w") as json_file:
        json.dump(data, json_file, indent=4)

    
# Creazione della finestra principale
root = tk.Tk()
root.title("Directory Scanner App")

# Creazione di un frame per contenere i bottoni
button_frame = tk.Frame(root)
button_frame.pack()

# Creazione dei campi di input e dei bottoni
input_frame = tk.Frame(button_frame)
input_frame.pack(side="left")

search_label = tk.Label(input_frame, text="Cerca Directory:")
search_label.pack(side="left", padx=5, pady=5)

search_entry = tk.Entry(input_frame)
search_entry.pack(side="left", padx=5, pady=5)
# Associa la funzione search_directory all'evento di pressione del tasto "Invio"
search_entry.bind("<Return>", search_directory)

search_button = tk.Button(button_frame, text="Cerca", command=search_directory)
search_button.pack(side="left", padx=5, pady=5)

select_button = tk.Button(button_frame, text="Seleziona Directory", command=select_directory)
select_button.pack(side="left", padx=5, pady=5)

show_all_button = tk.Button(button_frame, text="Mostra Tutti", command=lambda: show_all_items(show_files_var.get()))
show_all_button.pack(side="left", padx=5, pady=5)

clear_database_button = tk.Button(button_frame, text="Svuota Database", command=clear_database)
clear_database_button.pack(side="left", padx=5, pady=5)

#auto_scan_button = tk.Button(button_frame, text="Scansione Automatica", command=lambda: scan_directories_from_config('directories.txt'))
auto_scan_button = tk.Button(button_frame, text="Scansione Automatica", command=start_auto_scan)
auto_scan_button.pack(side="left", padx=5, pady=5)

view_configurations_button = tk.Button(button_frame, text="Visualizza Configurazioni", command=open_configurations_window)
view_configurations_button.pack(side="left", padx=5, pady=5)




# Creazione dell'oggetto per l'opzione "Show Files"
show_files_var = tk.BooleanVar()
show_files_checkbutton = tk.Checkbutton(button_frame, text="Show Files", variable=show_files_var)
show_files_checkbutton.pack(side="left", padx=5, pady=5)

# Associa la funzione di ricerca al cambiamento dello stato dell'opzione
show_files_var.trace_add("write", lambda *args: search_directory(show_files_var.get()))



# Creazione di un frame per contenere la tabella e le barre di scorrimento
frame = ttk.Frame(root)
frame.pack(fill="both", expand=True)

# Creazione della tabella per i risultati
tree = ttk.Treeview(frame, columns=("Directory"))
tree.column("#0", width=0, stretch=tk.NO)  # Imposta la colonna vuota a larghezza 0
tree.column("#1", width=1000, anchor="w")
tree.heading("#1", text="Directory")
tree.tag_configure("directory", font=("Helvetica", 10, "bold"))

# Abilita le barre di scorrimento verticale e orizzontale
vertical_scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
horizontal_scrollbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
tree.configure(yscrollcommand=vertical_scrollbar.set, xscrollcommand=horizontal_scrollbar.set)

# Aggiungi la tabella e le barre di scorrimento al frame
tree.grid(row=0, column=0, sticky="nsew")
vertical_scrollbar.grid(row=0, column=1, sticky="ns")
horizontal_scrollbar.grid(row=1, column=0, sticky="ew")

# Crea un menu contestuale
context_menu = tk.Menu(tree, tearoff=0)
context_menu.add_command(label="Elimina dal DB", command=delete_selected_item)
tree.bind("<Button-3>", show_context_menu)  # Associa il menu contestuale al tasto destro del mouse

# Fai in modo che il frame si espanda correttamente
frame.grid_rowconfigure(0, weight=1)
frame.grid_columnconfigure(0, weight=1)

# Creazione della barra di avanzamento
progress_bar = ttk.Progressbar(root, orient="horizontal", mode="determinate")
progress_bar.pack(fill=tk.X)

# Etichetta per lo stato della scansione
status_label = tk.Label(root, text="")
status_label.pack()

info_label = tk.Label(root, text="Numero di righe nel database: 0")
info_label.pack(side="right")


# Associa la funzione di gestione dell'evento di doppio clic alla tabella
tree.bind("<Double-1>", on_tree_double_click)

update_info_label() 

root.mainloop()
