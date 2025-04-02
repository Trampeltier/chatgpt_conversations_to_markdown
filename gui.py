import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import json
import os
import subprocess

CONFIG_FILE = "config.json"

DEFAULT_CONFIG = {
    "user_name": "Me",
    "LLM_name": "ChatGPT",
    "input_directory": "./chatgptexport",
    "output_directory": "./output",
    "date_format": "%Y-%m-%d",
    "time_format": "%H:%M",
    "include_date": True,
    "include_timestamps": True,
    "prefix_date_in_filename": True,
    "convert_latex_syntax": True,
    "message_separator": "\n\n---\n\n",
    "skip_empty_messages": True,
    "collapse_long_messages": True,
    "long_message_line_threshold": 5,
    "collapse_open_by_default": False,
    "obsidian_front_matter": True
}

TOOLTIPS = {
    "user_name": "Name shown as the human author of messages.",
    "LLM_name": "Name shown as the AI assistant (e.g., ChatGPT).",
    "input_directory": "Folder where the exported ChatGPT JSON and image files are located.",
    "output_directory": "Folder where converted Markdown files will be saved.",
    "date_format": "Format for displaying the conversation date (e.g., %Y-%m-%d).",
    "time_format": "Format for message timestamps (e.g., %H:%M).",
    "include_date": "Include the date at the top of the Markdown file.",
    "include_timestamps": "Include time below each message.",
    "prefix_date_in_filename": "Prefix the output file name with the conversation date.",
    "convert_latex_syntax": "Convert \\(x\\) to $x$ and \\[x\\] to $$x$$.",
    "message_separator": "Text inserted between each message (e.g., Markdown divider).",
    "skip_empty_messages": "Ignore messages with no content.",
    "collapse_long_messages": "Collapse long messages in Markdown using <details>.",
    "long_message_line_threshold": "Number of lines after which a message is considered long.",
    "collapse_open_by_default": "If true, collapsible messages will be expanded by default.",
    "obsidian_front_matter": "Include YAML frontmatter compatible with Obsidian."
}

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def show(self, event=None):
        if self.tip_window or not self.text:
            return
        x, y, _, cy = self.widget.bbox("insert") or (0, 0, 0, 0)
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.geometry(f"+{x}+{y}")
        label = ttk.Label(tw, text=self.text, justify='left',
                         background="#ffffe0", relief='solid', borderwidth=1,
                         font=("Segoe UI", "9", "normal"), wraplength=300)
        label.pack(ipadx=1)

    def hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None


class ConfigGUI:
    def __init__(self, root):
        self.root = root
        root.title("ChatGPT Markdown Export Config")
        self.fields = {}

        self.config = self.load_config()
        self.build_form()

        tk.Button(root, text="Run", command=self.run).pack(pady=5)
        tk.Button(root, text="Reset to Defaults", command=self.reset).pack()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return DEFAULT_CONFIG.copy()

    def build_form(self):
        frame = ttk.Frame(self.root)
        frame.pack(padx=10, pady=10)

        for key, value in self.config.items():
            label = ttk.Label(frame, text=key)
            label.grid(row=len(self.fields), column=0, sticky='w', pady=2)
            ToolTip(label, TOOLTIPS.get(key, ""))


            if isinstance(value, bool):
                var = tk.BooleanVar(value=value)
                checkbox = ttk.Checkbutton(frame, variable=var)
                checkbox.grid(row=len(self.fields), column=1, sticky='w')
                self.fields[key] = var
            elif isinstance(value, int):
                var = tk.StringVar(value=str(value))
                entry = ttk.Entry(frame, textvariable=var, width=10)
                entry.grid(row=len(self.fields), column=1, sticky='w')
                self.fields[key] = var
            elif key == "message_separator":
                txt = scrolledtext.ScrolledText(frame, height=8, width=30)
                txt.insert(tk.END, value.encode('unicode_escape').decode())
                txt.grid(row=len(self.fields), column=1, sticky='w')
                self.fields[key] = txt
            elif key in ("input_directory", "output_directory"):
                var = tk.StringVar(value=value)
                entry = ttk.Entry(frame, textvariable=var, width=30)
                entry.grid(row=len(self.fields), column=1, sticky='w')
                button = ttk.Button(frame, text="Browse", command=lambda v=var: self.browse_folder(v))
                button.grid(row=len(self.fields), column=2, padx=5)
                self.fields[key] = var

            else:
                var = tk.StringVar(value=value)
                entry = ttk.Entry(frame, textvariable=var, width=40)
                entry.grid(row=len(self.fields), column=1, sticky='w')
                self.fields[key] = var

    def collect_config(self):
        result = {}
        for key, widget in self.fields.items():
            
            if isinstance(widget, tk.BooleanVar):
                result[key] = widget.get()
            elif isinstance(widget, scrolledtext.ScrolledText):
                raw = widget.get("1.0", tk.END).strip()
                result[key] = raw.encode('utf-8').decode('unicode_escape')
            else:
                value = widget.get()
                if key == "long_message_line_threshold":
                    try:
                        result[key] = int(value)
                    except ValueError:
                        result[key] = DEFAULT_CONFIG[key]
                else:
                    result[key] = value
        return result

    def run(self):
        config = self.collect_config()
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        try:
            subprocess.run([sys.executable, "conversion.py"], check=True)
            messagebox.showinfo("Success", "Conversion completed successfully.")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to run conversion.py:\n{e}")

    def reset(self):
        if os.path.exists(CONFIG_FILE):
            os.remove(CONFIG_FILE)
        self.config = DEFAULT_CONFIG.copy()
        for widget in self.root.winfo_children():
            widget.destroy()
        self.fields = {}
        self.build_form()
        ttk.Button(self.root, text="Run", command=self.run).pack(pady=5)
        ttk.Button(self.root, text="Reset to Defaults", command=self.reset).pack()
    def browse_folder(self, var):
        folder = filedialog.askdirectory()
        if folder:
            var.set(folder)


if __name__ == "__main__":
    import sys
    root = tk.Tk()
    style = ttk.Style()

    # Try using a modern theme
    for theme in ["vista", "xpnative", "clam", "alt", "default"]:
        if theme in style.theme_names():
            print(theme)
            style.theme_use(theme)
            style.configure('.', font=('Segoe UI', 12))
            style.configure('TButton', padding=6)
            style.configure('TCheckbutton', padding=2)

            break
    gui = ConfigGUI(root)
    root.mainloop()
