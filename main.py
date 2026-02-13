import os
import sqlite3
import pandas as pd
from datetime import datetime
import shutil
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import webbrowser
import platform
import socket
import psutil

#  Forensic Helper Functions
def convert_chrome_time(chrome_time):
    """Convert Chrome timestamp to datetime"""
    return datetime(1601, 1, 1) + pd.to_timedelta(chrome_time, unit='us')

def convert_firefox_time(firefox_time):
    """Convert Firefox timestamp to datetime"""
    return datetime(1970, 1, 1) + pd.to_timedelta(firefox_time, unit='us')

#  Browser Artifact Functions
def get_chrome_history():
    path = os.path.expanduser(r'~\AppData\Local\Google\Chrome\User Data\Default\History')
    if not os.path.exists(path):
        return pd.DataFrame()
    temp = 'chrome_history_temp'
    shutil.copy2(path, temp)
    conn = sqlite3.connect(temp)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title, visit_count, last_visit_time FROM urls")
    data = [[url, title, visit_count, convert_chrome_time(last_visit_time)]
            for url, title, visit_count, last_visit_time in cursor.fetchall()]
    conn.close()
    os.remove(temp)
    return pd.DataFrame(data, columns=['URL', 'Title', 'Visit Count', 'Last Visited']).sort_values(by='Last Visited', ascending=False)

def get_firefox_history():
    profile_dir = os.path.expanduser(r'~\AppData\Roaming\Mozilla\Firefox\Profiles')
    if not os.path.exists(profile_dir):
        return pd.DataFrame()
    profiles = [f for f in os.listdir(profile_dir) if os.path.isdir(os.path.join(profile_dir, f))]
    if not profiles:
        return pd.DataFrame()
    db = os.path.join(profile_dir, profiles[0], 'places.sqlite')
    if not os.path.exists(db):
        return pd.DataFrame()
    temp = 'firefox_history_temp.sqlite'
    shutil.copy2(db, temp)
    conn = sqlite3.connect(temp)
    cursor = conn.cursor()
    cursor.execute("SELECT url, title, visit_count, last_visit_date FROM moz_places WHERE url NOT NULL")
    data = []
    for url, title, visit_count, last_visit_date in cursor.fetchall():
        last_visit_date = last_visit_date or 0
        data.append([url, title, visit_count, convert_firefox_time(last_visit_date)])
    conn.close()
    os.remove(temp)
    return pd.DataFrame(data, columns=['URL', 'Title', 'Visit Count', 'Last Visited']).sort_values(by='Last Visited', ascending=False)

def get_chrome_bookmarks():
    path = os.path.expanduser(r'~\AppData\Local\Google\Chrome\User Data\Default\Bookmarks')
    if not os.path.exists(path):
        return pd.DataFrame()
    import json
    with open(path, 'r', encoding='utf-8') as f:
        bookmarks_data = json.load(f)
    def extract_bookmarks(node):
        items = []
        if 'children' in node:
            for child in node['children']:
                items.extend(extract_bookmarks(child))
        if node.get('type') == 'url':
            items.append([node.get('name', ''), node.get('url', '')])
        return items
    data = extract_bookmarks(bookmarks_data['roots']['bookmark_bar'])
    return pd.DataFrame(data, columns=['Title', 'URL'])

def get_system_info():
    info = {
        'Username': os.getlogin(),
        'Hostname': socket.gethostname(),
        'OS': platform.system() + " " + platform.release(),
        'Architecture': platform.architecture()[0],
        'CPU Cores': psutil.cpu_count(logical=True),
        'RAM (GB)': round(psutil.virtual_memory().total / 1024**3, 2),
        'IP Address': socket.gethostbyname(socket.gethostname())
    }
    return info

#  GUI Functions
def load_all_data():
    chrome_hist = get_chrome_history()
    firefox_hist = get_firefox_history()
    bookmarks = get_chrome_bookmarks()
    combined_history = pd.concat([chrome_hist, firefox_hist], ignore_index=True)
    root.data_history = combined_history
    root.data_bookmarks = bookmarks
    root.system_info = get_system_info()
    # Populate tabs
    populate_tree(tree_history, combined_history)
    populate_tree(tree_bookmarks, bookmarks)
    populate_system_info()
    messagebox.showinfo("Loaded", "All data loaded successfully!")

def populate_tree(tree, df):
    tree.delete(*tree.get_children())
    for idx, row in df.iterrows():
        tree.insert("", "end", values=list(row))

def populate_system_info():
    tree_sys.delete(*tree_sys.get_children())
    for key, value in root.system_info.items():
        tree_sys.insert("", "end", values=(key, value))

def search_history(event=None):
    if not hasattr(root, 'data_history'):
        return
    text = search_var.get().lower()
    df = root.data_history
    filtered = df[df['URL'].str.lower().str.contains(text) | df['Title'].str.lower().str.contains(text)]
    populate_tree(tree_history, filtered)

def search_bookmarks(event=None):
    if not hasattr(root, 'data_bookmarks'):
        return
    text = search_var_bookmarks.get().lower()
    df = root.data_bookmarks
    filtered = df[df['URL'].str.lower().str.contains(text) | df['Title'].str.lower().str.contains(text)]
    populate_tree(tree_bookmarks, filtered)

def export_csv_tree(df, default_name):
    if df.empty:
        messagebox.showwarning("Warning", "No data to export!")
        return
    filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")], initialfile=default_name)
    if filepath:
        df.to_csv(filepath, index=False)
        messagebox.showinfo("Saved", f"Exported to {filepath}")

def open_url_tree(event, tree, col_index=0):
    selected = tree.focus()
    if selected:
        url = tree.item(selected)['values'][col_index]
        webbrowser.open(url)

#  Tkinter GUI
root = tk.Tk()
root.title("Advanced Forensic Analyzer")
root.geometry("1000x600")

tab_control = ttk.Notebook(root)
tab_history = ttk.Frame(tab_control)
tab_bookmarks = ttk.Frame(tab_control)
tab_system = ttk.Frame(tab_control)
tab_control.add(tab_history, text='Browser History')
tab_control.add(tab_bookmarks, text='Bookmarks')
tab_control.add(tab_system, text='System Info')
tab_control.pack(expand=1, fill="both")

# Top Frame buttons
btn_frame = tk.Frame(root)
btn_frame.pack(fill="x", pady=5)
load_btn = tk.Button(btn_frame, text="Load All Data", command=load_all_data)
load_btn.pack(side="left", padx=5)
export_btn = tk.Button(btn_frame, text="Export History CSV", command=lambda: export_csv_tree(root.data_history, "history.csv"))
export_btn.pack(side="left", padx=5)
export_bm_btn = tk.Button(btn_frame, text="Export Bookmarks CSV", command=lambda: export_csv_tree(root.data_bookmarks, "bookmarks.csv"))
export_bm_btn.pack(side="left", padx=5)

# History Tab
search_var = tk.StringVar()
search_entry = tk.Entry(tab_history, textvariable=search_var)
search_entry.pack(fill="x", padx=5, pady=2)
search_entry.bind("<KeyRelease>", search_history)
columns_hist = ("URL","Title","Visit Count","Last Visited")
tree_history = ttk.Treeview(tab_history, columns=columns_hist, show="headings")
tree_history.pack(fill="both", expand=True)
for col in columns_hist:
    tree_history.heading(col, text=col)
tree_history.bind("<Double-1>", lambda e: open_url_tree(e, tree_history))

# Bookmarks Tab
search_var_bookmarks = tk.StringVar()
search_entry_bm = tk.Entry(tab_bookmarks, textvariable=search_var_bookmarks)
search_entry_bm.pack(fill="x", padx=5, pady=2)
search_entry_bm.bind("<KeyRelease>", search_bookmarks)
columns_bm = ("Title","URL")
tree_bookmarks = ttk.Treeview(tab_bookmarks, columns=columns_bm, show="headings")
tree_bookmarks.pack(fill="both", expand=True)
for col in columns_bm:
    tree_bookmarks.heading(col, text=col)
tree_bookmarks.bind("<Double-1>", lambda e: open_url_tree(e, tree_bookmarks, col_index=1))

# System Info Tab
columns_sys = ("Property","Value")
tree_sys = ttk.Treeview(tab_system, columns=columns_sys, show="headings")
tree_sys.pack(fill="both", expand=True)
for col in columns_sys:
    tree_sys.heading(col, text=col)

root.mainloop()
