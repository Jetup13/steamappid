import requests
import json
import os
import re
import tkinter as tk
from tkinter import messagebox, simpledialog
from concurrent.futures import ThreadPoolExecutor, as_completed

# === Sanitize Function ===
def sanitize_filename(name):
    original_name = name

    # Fix colons stuck to letters: add space only if missing
    name = re.sub(r'(\S):(\S)', r'\1 : \2', name)      # colon between letters
    name = re.sub(r'(\S)\s*:\s*(\S)', r'\1 : \2', name) # ensure proper spacing

    # Replace other illegal characters
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
    name = name.strip().rstrip('.')

    # Reserved Windows names
    reserved = {
        'CON', 'PRN', 'AUX', 'NUL',
        *(f'COM{i}' for i in range(1, 10)),
        *(f'LPT{i}' for i in range(1, 10))
    }
    if name.upper() in reserved:
        name += '_'

    changed = name != original_name
    return name, changed

# === Globals ===
steam_data = []
store_data = []
changes_log = []
output_dir = os.getcwd()
user_library_file = os.path.join(output_dir, "user_steam_games.json")
store_cache_file = os.path.join(output_dir, "all_steam_store_games.json")

# === Steam Library Functions ===
def grab_user_library():
    global steam_data
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

# === Image Download Functions ===
def download_single_image(app, quality, covers_folder):
    name = app.get("name", "").strip()
    appid = app.get("appid")
    capsule_filename = app.get("capsule_filename")
    if not name or not capsule_filename:
        return None

    sanitized_name, _ = sanitize_filename(name)

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

# === File Generation Functions ===
def generate_files(mode="esde", data_source=None, log_prefix=""):
    global changes_log
    if data_source is None:
        messagebox.showerror("Error", "No data provided for file generation.")
        return

    folder_name = "steam" if mode == "esde" else "steam_daijishou"
    if log_prefix == "store":
        folder_name = "steam_store" if mode == "esde" else "steam_store_daijishou"

    # For store files, ask user how many to generate
    limit = len(data_source)
    if log_prefix == "store":
        total_games = len(data_source)
        limit = simpledialog.askinteger(
            "Generate Store Files",
            f"Total store games: {total_games}\nEnter number of files to generate (0 = all):",
            minvalue=0,
            maxvalue=total_games
        )
        if limit is None:
            return
        if limit == 0:
            limit = total_games
        if limit > 5000:
            proceed = messagebox.askyesno(
                "Warning",
                f"You are about to generate {limit} files. This may take a long time and use a lot of disk space. Continue?"
            )
            if not proceed:
                return

    output_folder = os.path.join(output_dir, folder_name)
    os.makedirs(output_folder, exist_ok=True)
    changes_log = []
    name_check = {}

    for app in data_source[:limit]:
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

    # Save log
    log_file = f"changednames{('_' + log_prefix) if log_prefix else ''}.txt"
    log_path = os.path.join(output_dir, log_file)
    with open(log_path, "w", encoding="utf-8") as log:
        if changes_log:
            log.write("\n".join(changes_log))
        else:
            log.write("No filenames required sanitization or renaming.\n")

    msg_label = "ES-DE" if mode == "esde" else "Daijishou"
    messagebox.showinfo("Done", f"Generated {len(name_check)} {msg_label} files.\nLog: {log_path}")

def generate_esde_files():
    generate_files("esde", steam_data)

def generate_daijishou_files():
    generate_files("daijishou", steam_data)

def generate_store_esde_files():
    generate_files("esde", store_data, log_prefix="store")

def generate_store_daijishou_files():
    generate_files("daijishou", store_data, log_prefix="store")

# === Grab All Store Games with cache and incremental updates ===
def grab_all_store_games(force_refresh=False):
    global store_data
    token = token_entry.get().strip()
    if not token:
        messagebox.showerror("Error", "Please enter your Access Token.")
        return

    # Load cache if available
    if os.path.exists(store_cache_file) and not force_refresh:
        use_cache = messagebox.askyesno("Cache Found", "Cached store list found. Use cached version?")
        if use_cache:
            with open(store_cache_file, "r", encoding="utf-8") as f:
                store_data = json.load(f)
            messagebox.showinfo("Info", f"Loaded {len(store_data)} games from cache.")
            # Determine last appid from cache
            last_appid = max((app.get("appid", 0) for app in store_data), default=0)
            more_results = True
        else:
            store_data = []
            last_appid = 0
            more_results = True
    else:
        store_data = []
        last_appid = 0
        more_results = True

    try:
        while more_results:
            url = f"https://api.steampowered.com/IStoreService/GetAppList/v1/?access_token={token}&include_games=true"
            if last_appid > 0:
                url += f"&last_appid={last_appid}"

            r = requests.get(url, timeout=60)
            data = r.json()
            apps = data.get("response", {}).get("apps", [])
            more_results = data.get("response", {}).get("have_more_results", False)
            last_appid = data.get("response", {}).get("last_appid", last_appid)

            for app in apps:
                # Avoid duplicates in case cache already has some
                if all(existing.get("appid") != app.get("appid") for existing in store_data):
                    store_data.append({
                        "appid": app.get("appid"),
                        "name": app.get("name", "")
                    })

        # Save cache
        with open(store_cache_file, "w", encoding="utf-8") as f:
            json.dump(store_data, f, indent=2, ensure_ascii=False)

        messagebox.showinfo("Success", f"Downloaded {len(store_data)} store games.\nCached at:\n{store_cache_file}")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to download store games:\n{e}")

# === GUI ===
root = tk.Tk()
root.title("Steam User Library Generator")
root.geometry("500x600")
root.resizable(False, False)

# === Tk Variables must be created after root ===
download_images_var = tk.IntVar()  # 0 = no, 1 = yes
image_quality_var = tk.StringVar(value="high")  # 'low' or 'high'

tk.Label(root, text="Steam User Library Generator", font=("Segoe UI", 14, "bold")).pack(pady=10)

tk.Label(root, text="Access Token:").pack()
token_entry = tk.Entry(root, width=50)
token_entry.pack(pady=5)

tk.Label(root, text="SteamID:").pack()
steamid_entry = tk.Entry(root, width=50)
steamid_entry.pack(pady=5)

tk.Button(root, text="Grab User Steam Library", command=grab_user_library, width=40).pack(pady=10)
tk.Button(root, text="Generate ES-DE Files", command=generate_esde_files, width=40).pack(pady=5)
tk.Button(root, text="Generate Daijishou Files", command=generate_daijishou_files, width=40).pack(pady=5)

# === Image Options ===
tk.Checkbutton(root, text="Download Images", variable=download_images_var).pack(pady=10)
tk.Label(root, text="Image Quality:").pack()
tk.Radiobutton(root, text="Low Quality", variable=image_quality_var, value="low").pack()
tk.Radiobutton(root, text="High Quality", variable=image_quality_var, value="high").pack()

# === Steam Store Section ===
tk.Label(root, text="--- Steam Store Games ---", font=("Segoe UI", 12, "bold")).pack(pady=10)
tk.Button(root, text="Grab All Store Games", command=grab_all_store_games, width=40).pack(pady=5)
tk.Button(root, text="Force Full Refresh Store List", command=lambda: grab_all_store_games(force_refresh=True), width=40).pack(pady=5)
tk.Button(root, text="Generate ES-DE Store Files", command=generate_store_esde_files, width=40).pack(pady=5)
tk.Button(root, text="Generate Daijishou Store Files", command=generate_store_daijishou_files, width=40).pack(pady=5)

root.mainloop()
