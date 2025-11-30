import json
import os
import re
import tkinter as tk
from tkinter import messagebox, ttk

# === Globals ===
store_data = []
output_dir = os.getcwd()
store_library_file = os.path.join(output_dir, "all_steam_store_games.json")

# === Sanitize Function ===
def sanitize_filename(name):
    original_name = name

    # Replace colon with spaced dash
    name = re.sub(r'\s*:\s*', ' - ', name)

    # Replace other forbidden Windows characters
    replacements = {
        '\\': '_',
        '/': '_',
        '*': '_',
        '?': '',
        '"': "'",
        '<': '(',
        '>': ')',
        '|': '',
    }
    for bad, good in replacements.items():
        name = name.replace(bad, good)

    # Remove special trademark characters
    name = re.sub(r'(\(TM\)|™|â„ |®|©)', '', name, flags=re.IGNORECASE)

    # Normalize spaces
    name = re.sub(r'\s+', ' ', name).strip()

    # Prevent trailing dots
    name = name.rstrip('.')

    # Reserved device names on Windows
    reserved = {
        'CON', 'PRN', 'AUX', 'NUL',
        *(f'COM{i}' for i in range(1, 10)),
        *(f'LPT{i}' for i in range(1, 10))
    }
    if name.upper() in reserved:
        name += '_'

    return name

# === Load Store Data ===
def load_store_data():
    global store_data
    if not os.path.exists(store_library_file):
        messagebox.showerror("Error", f"Store data file not found:\n{store_library_file}\n\nPlease run the main generator first to download the store list.")
        return False
    
    try:
        with open(store_library_file, "r", encoding="utf-8") as f:
            store_data = json.load(f)
        status_label.config(text=f"Loaded {len(store_data):,} games from store database")
        return True
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load store data:\n{e}")
        return False

# === Search Function ===
def search_games(event=None):
    query = search_entry.get().strip().lower()
    results_listbox.delete(0, tk.END)
    
    if len(query) < 2:
        status_label.config(text="Type at least 2 characters to search")
        return
    
    matches = []
    for game in store_data:
        name = game.get("name", "").lower()
        if query in name:
            matches.append(game)
            if len(matches) >= 500:  # Limit results for performance
                break
    
    for game in matches:
        display_name = f"{game.get('name', 'Unknown')} (AppID: {game.get('appid', 'N/A')})"
        results_listbox.insert(tk.END, display_name)
    
    status_label.config(text=f"Found {len(matches)} match{'es' if len(matches) != 1 else ''}" + 
                        (" (showing first 500)" if len(matches) >= 500 else ""))

# === Get Selected Game ===
def get_selected_game():
    selection = results_listbox.curselection()
    if not selection:
        messagebox.showwarning("No Selection", "Please select a game from the search results.")
        return None
    
    index = selection[0]
    display_text = results_listbox.get(index)
    
    # Extract game name (everything before the last " (AppID:")
    game_name = display_text.rsplit(" (AppID:", 1)[0]
    
    # Find the matching game in store_data
    for game in store_data:
        if game.get("name") == game_name:
            return game
    
    return None

# === Generate ES-DE File ===
def generate_esde_file():
    game = get_selected_game()
    if not game:
        return
    
    name = game.get("name", "Unknown")
    appid = game.get("appid", 0)
    
    sanitized_name = sanitize_filename(name)
    output_folder = os.path.join(output_dir, "steam")
    os.makedirs(output_folder, exist_ok=True)
    
    file_path = os.path.join(output_folder, f"{sanitized_name}.steam")
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(str(appid))
        
        messagebox.showinfo("Success", f"Created ES-DE file:\n{file_path}")
        status_label.config(text=f"Generated: {sanitized_name}.steam")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create file:\n{e}")

# === Generate Daijishou File ===
def generate_daijishou_file():
    game = get_selected_game()
    if not game:
        return
    
    name = game.get("name", "Unknown")
    appid = game.get("appid", 0)
    
    sanitized_name = sanitize_filename(name)
    output_folder = os.path.join(output_dir, "steam_daijishou")
    os.makedirs(output_folder, exist_ok=True)
    
    file_path = os.path.join(output_folder, f"{sanitized_name}.steamappid")
    
    content = f"# Daijishou Player Template\n[steamappid] {appid}\n..."
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        messagebox.showinfo("Success", f"Created Daijishou file:\n{file_path}")
        status_label.config(text=f"Generated: {sanitized_name}.steamappid")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to create file:\n{e}")

# === Clear Search ===
def clear_search():
    search_entry.delete(0, tk.END)
    results_listbox.delete(0, tk.END)
    status_label.config(text="Enter a game name to search")

# === GUI Setup ===
root = tk.Tk()
root.title("Steam Game File Generator")
root.geometry("700x600")
root.resizable(True, True)

# Title
tk.Label(root, text="Steam Game File Generator", font=("Segoe UI", 14, "bold")).pack(pady=10)

# Search Frame
search_frame = tk.Frame(root)
search_frame.pack(pady=10, padx=20, fill="x")

tk.Label(search_frame, text="Search Game:", font=("Segoe UI", 10)).pack(side="left", padx=(0, 10))
search_entry = tk.Entry(search_frame, font=("Segoe UI", 10))
search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
search_entry.bind("<KeyRelease>", search_games)

tk.Button(search_frame, text="Clear", command=clear_search, width=8).pack(side="left")

# Results Frame
results_frame = tk.Frame(root)
results_frame.pack(pady=10, padx=20, fill="both", expand=True)

tk.Label(results_frame, text="Search Results:", font=("Segoe UI", 10, "bold")).pack(anchor="w")

# Scrollbar and Listbox
scrollbar = tk.Scrollbar(results_frame)
scrollbar.pack(side="right", fill="y")

results_listbox = tk.Listbox(results_frame, font=("Segoe UI", 9), yscrollcommand=scrollbar.set, height=15)
results_listbox.pack(side="left", fill="both", expand=True)
scrollbar.config(command=results_listbox.yview)

# Button Frame
button_frame = tk.Frame(root)
button_frame.pack(pady=10)

tk.Button(button_frame, text="Generate ES-DE File (.steam)", command=generate_esde_file, 
          width=25, height=2, font=("Segoe UI", 10, "bold"), bg="#4CAF50", fg="white").pack(side="left", padx=10)

tk.Button(button_frame, text="Generate Daijishou File (.steamappid)", command=generate_daijishou_file,
          width=30, height=2, font=("Segoe UI", 10, "bold"), bg="#2196F3", fg="white").pack(side="left", padx=10)

# Status Bar
status_label = tk.Label(root, text="Loading store database...", font=("Segoe UI", 9), 
                       relief="sunken", anchor="w", bg="#f0f0f0")
status_label.pack(side="bottom", fill="x", pady=(10, 0))

# Info Label
info_text = "Select a game from the search results, then click a button to generate the file."
tk.Label(root, text=info_text, font=("Segoe UI", 9), fg="gray").pack(side="bottom", pady=5)

# Load data on startup
root.after(100, load_store_data)

root.mainloop()