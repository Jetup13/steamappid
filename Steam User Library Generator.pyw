import requests
import json
import os
import re
import tkinter as tk
from tkinter import messagebox
from tkinter.simpledialog import askinteger
from concurrent.futures import ThreadPoolExecutor, as_completed

# === Globals ===
steam_data = []
store_data = []
changes_log = []
output_dir = os.getcwd()
user_library_file = os.path.join(output_dir, "user_steam_games.json")
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
    name = re.sub(r'(\(TM\)|™|℠|®|©)', '', name, flags=re.IGNORECASE)

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

    changed = name != original_name
    return name, changed

# === Button Functions ===
def grab_user_library():
    global steam_data

    # Load cached if exists
    if os.path.exists(user_library_file):
        try:
            with open(user_library_file, "r", encoding="utf-8") as f:
                steam_data = json.load(f)
            messagebox.showinfo("Loaded", f"Loaded cached user library:\n{user_library_file}")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load cached user library:\n{e}")
            return

    token = token_entry.get().strip()
    steamid = steamid_entry.get().strip()
    if not token or not steamid:
        messagebox.showerror("Error", "Please enter both Access Token and SteamID.")
        return

    url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?access_token={token}&steamid={steamid}&include_appinfo=true&include_played_free_games=true&include_free_sub=false&include_extended_appinfo=true"
    try:
        messagebox.showinfo("Info", "Downloading user Steam library...")
        r = requests.get(url, timeout=60)
        data = r.json()
        games = data.get("response", {}).get("games", [])
        steam_data = []
        for g in games:
            steam_data.append({
                "appid": g.get("appid"),
                "name": g.get("name", ""),
                "capsule_filename": g.get("capsule_filename", "")
            })
        # Save user library
        with open(user_library_file, "w", encoding="utf-8") as f:
            json.dump(steam_data, f, indent=2, ensure_ascii=False)
        messagebox.showinfo("Success", f"Downloaded {len(steam_data)} games. Saved to:\n{user_library_file}")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to download library:\n{e}")

# === Image Download Helper for ThreadPool ===
def download_single_image(app, quality, covers_folder):
    name = app.get("name", "").strip()
    appid = app.get("appid")
    capsule_filename = app.get("capsule_filename")
    if not name or not capsule_filename:
        return None

    sanitized_name, _ = sanitize_filename(name)

    # Construct image URL
    if quality == "high":
        base, ext = os.path.splitext(capsule_filename)
        image_url = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/{base}_2x{ext}"
    else:
        image_url = f"https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/{capsule_filename}"

    img_path = os.path.join(covers_folder, f"{sanitized_name}.jpg")
    try:
        r = requests.get(image_url, timeout=30)
        if r.status_code == 200:
            with open(img_path, "wb") as f:
                f.write(r.content)
            return sanitized_name
    except Exception as e:
        changes_log.append(f"FAILED TO DOWNLOAD IMAGE: {sanitized_name} ({e})")
    return None

# === Download Images Function (Parallel) ===
def download_images():
    global steam_data
    if not steam_data:
        messagebox.showerror("Error", "No Steam library loaded.")
        return

    covers_folder = os.path.join(output_dir, "covers")
    os.makedirs(covers_folder, exist_ok=True)
    count = 0

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(download_single_image, app, image_quality_var.get(), covers_folder)
                   for app in steam_data]
        for future in as_completed(futures):
            result = future.result()
            if result:
                count += 1

    messagebox.showinfo("Done", f"Downloaded {count} images to:\n{covers_folder}")

# === Generate Files Function ===
def generate_files(mode="esde", use_store=False, limit=None):
    global changes_log, steam_data, store_data
    data_source = store_data if use_store else steam_data

    if not data_source:
        messagebox.showerror("Error", "No Steam library loaded.")
        return

    folder_name = "steam_store" if use_store else ("steam" if mode == "esde" else "steam_daijishou")
    output_folder = os.path.join(output_dir, folder_name)
    os.makedirs(output_folder, exist_ok=True)
    changes_log = []
    name_check = {}

    if use_store and limit:
        data_source = data_source[:limit]

    for app in data_source:
        name = app.get("name", "").strip()
        appid = app.get("appid", 0)
        if not name:
            continue

        sanitized, changed = sanitize_filename(name)

        # Handle duplicates
        final_name = sanitized
        counter = 1
        while final_name.lower() in name_check:
            counter += 1
            final_name = f"{sanitized} ({counter})"
            changed = True
        name_check[final_name.lower()] = True

        if changed:
            changes_log.append(f"{name} -> {final_name}")

        if mode == "esde":
            file_ext = ".steam"
            content = str(appid)
        else:
            file_ext = ".steamappid"
            content = f"# Daijishou Player Template\n[steamappid] {appid}\n..."

        file_path = os.path.join(output_folder, f"{final_name}{file_ext}")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            changes_log.append(f"FAILED TO CREATE: {final_name} ({e})")

    # Save unified change log
    log_path = os.path.join(output_dir, "changednames.txt")
    with open(log_path, "w", encoding="utf-8") as log:
        if changes_log:
            log.write("\n".join(changes_log))
        else:
            log.write("No filenames required sanitization or renaming.\n")

    # Download images in parallel (only for user library)
    if download_images_var.get() and not use_store:
        download_images()

    msg_label = "Store" if use_store else ("ES-DE" if mode == "esde" else "Daijishou")
    messagebox.showinfo("Done", f"Generated {len(name_check)} {msg_label} files.\nLog: {log_path}")

# === Wrapper Functions for User Library Buttons ===
def generate_esde_files():
    generate_files("esde", use_store=False)

def generate_daijishou_files():
    generate_files("daijishou", use_store=False)

# === Store Confirmation Dialog ===
def confirm_store_generation():
    if not store_data:
        messagebox.showerror("Error", "Please grab the Steam Store list first.")
        return None

    total_games = len(store_data)
    warning = f"You are about to generate files for {total_games} store games.\n"
    warning += "This can take a very long time and use a lot of disk space.\n"
    warning += "Do you want to limit the number of games generated?"

    # Ask Yes / No / Cancel
    result = messagebox.askyesnocancel("Warning", warning)
    if result is None:  # Cancel
        return None
    elif result:  # Yes -> limit files
        limit = askinteger("Limit Store Files",
                            "Enter the maximum number of games to generate:",
                            initialvalue=1000,
                            minvalue=1,
                            maxvalue=total_games)
        return limit
    else:  # No -> proceed with all, but ask extra confirmations
        # First confirmation
        if not messagebox.askyesno("Are you sure?", "You are about to generate ALL store files. Are you really sure?"):
            return None
        # Optional second confirmation
        if not messagebox.askyesno("Final confirmation", "This will generate potentially hundreds of thousands of files and may take hours. Continue?"):
            return None
        return total_games  # proceed with all files


# === Store File Buttons ===
def generate_store_esde_files():
    limit = confirm_store_generation()
    if limit is None:
        return
    generate_files("esde", use_store=True, limit=limit)

def generate_store_daijishou_files():
    limit = confirm_store_generation()
    if limit is None:
        return
    generate_files("daijishou", use_store=True, limit=limit)

# === Grab All Store Games ===
def grab_all_store_games():
    global store_data

    # Load cached if exists
    if os.path.exists(store_library_file):
        try:
            with open(store_library_file, "r", encoding="utf-8") as f:
                store_data = json.load(f)
            messagebox.showinfo("Loaded", f"Loaded cached full store list:\n{store_library_file}")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load cached store list:\n{e}")
            return

    token = token_entry.get().strip()
    if not token:
        messagebox.showerror("Error", "Please enter Access Token for store API.")
        return

    url_base = f"https://api.steampowered.com/IStoreService/GetAppList/v1/?access_token={token}&include_games=true"
    store_data = []
    last_appid = None
    messagebox.showinfo("Info", "Downloading full Steam store list. This may take a long time.")

    while True:
        url = url_base
        if last_appid:
            url += f"&last_appid={last_appid}"

        try:
            r = requests.get(url, timeout=60)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download store data:\n{e}")
            break

        apps = data.get("response", {}).get("apps", [])

        # Only store appid + name
        for a in apps:
            store_data.append({
                "appid": a.get("appid"),
                "name": a.get("name", "")
            })

        have_more = data.get("response", {}).get("have_more_results", False)
        last_appid = data.get("response", {}).get("last_appid")

        if not have_more:
            break

    # Save trimmed JSON
    with open(store_library_file, "w", encoding="utf-8") as f:
        json.dump(store_data, f, indent=2, ensure_ascii=False)

    messagebox.showinfo("Success", f"Downloaded {len(store_data)} store games.\nSaved to:\n{store_library_file}")
    
# === Widget ===

def paste_into(entry_widget):
    try:
        clipboard_text = root.clipboard_get()
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, clipboard_text)
    except:
        pass


# === GUI ===
root = tk.Tk()
root.title("Steam User Library Generator")
root.geometry("500x550")
root.resizable(False, False)

download_images_var = tk.IntVar()
image_quality_var = tk.StringVar(value="high")
store_limit_var = tk.IntVar(value=0)

tk.Label(root, text="Steam User Library Generator", font=("Segoe UI", 14, "bold")).pack(pady=10)

token_frame = tk.Frame(root)
token_frame.pack(pady=5)

tk.Label(token_frame, text="Access Token:").pack(side="left")
token_entry = tk.Entry(token_frame, width=40)
token_entry.pack(side="left", padx=5)

tk.Button(token_frame, text="Paste", command=lambda: paste_into(token_entry)).pack(side="left")

steamid_frame = tk.Frame(root)
steamid_frame.pack(pady=5)

tk.Label(steamid_frame, text="SteamID:").pack(side="left")
steamid_entry = tk.Entry(steamid_frame, width=40)
steamid_entry.pack(side="left", padx=5)

tk.Button(steamid_frame, text="Paste", command=lambda: paste_into(steamid_entry)).pack(side="left")

tk.Button(root, text="Grab User Steam Library", command=grab_user_library, width=40).pack(pady=10)
tk.Button(root, text="Generate ES-DE Files", command=generate_esde_files, width=40).pack(pady=5)
tk.Button(root, text="Generate Daijishou Files", command=generate_daijishou_files, width=40).pack(pady=5)

# === Image Options ===
tk.Checkbutton(root, text="Download Images", variable=download_images_var).pack(pady=10)
tk.Label(root, text="Image Quality:").pack()
tk.Radiobutton(root, text="Low Quality", variable=image_quality_var, value="low").pack()
tk.Radiobutton(root, text="High Quality", variable=image_quality_var, value="high").pack()

tk.Label(root, text="--- Steam Store Options ---\n (Advanced options)", font=("Segoe UI", 12, "bold")).pack(pady=10)
tk.Button(root, text="Grab All Steam Store Games", command=grab_all_store_games, width=40).pack(pady=5)
tk.Button(root, text="Generate ES-DE Files", command=generate_store_esde_files, width=40).pack(pady=5)
tk.Button(root, text="Generate Daijishou Files", command=generate_store_daijishou_files, width=40).pack(pady=5)

root.mainloop()
