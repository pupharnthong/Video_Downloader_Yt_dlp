import os
import sys
import shutil
import threading
import tkinter as tk
from tkinter import ttk
import yt_dlp

DOWNLOAD_DIR = os.path.expanduser("~/Downloads")

BG      = "#E3D6E7"
CARD_BG = "#7A5885"
TEXT    = "#230E29"
SUBTEXT = "#230E29"
ACCENT  = "#997171"
BTN_FG  = "#F9EDED"
BORDER  = "#EEE6E6"
SUCCESS = "#1FC6AD"
ERROR   = "#C0392B"
FONT    = "Helvetica"

def get_resource_path(relative_path):
    """Finds bundled files when running as an app"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

class VideoDownloaderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Downloader Naja")
        self.iconbitmap(get_resource_path("app_icon.ico"))
        self.configure(bg=BG)
        self.resizable(False, False)
        self.geometry("520x560")

        self._info = None
        self._dl_thread = None
        self._fetched = False

        self._build_ui()

    def _build_ui(self):
        wrap = tk.Frame(self, bg=BG, padx=36, pady=32)
        wrap.pack(fill="both", expand=True)

        tk.Label(wrap, text="Video Downloader", font=(FONT, 20, "bold"), bg=BG, fg=TEXT).pack(anchor="w")
        tk.Label(wrap, text="YouTube · MP4 (Video + Audio)", font=(FONT, 11), bg=BG, fg=SUBTEXT).pack(anchor="w", pady=(2, 20))

        card = tk.Frame(wrap, bg=CARD_BG, relief="flat", highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="x")
        inner = tk.Frame(card, bg=CARD_BG, padx=20, pady=20)
        inner.pack(fill="x")

        tk.Label(inner, text="Paste Link", font=(FONT, 11, "bold"), bg=CARD_BG, fg=TEXT).pack(anchor="w")
        url_row = tk.Frame(inner, bg=CARD_BG)
        url_row.pack(fill="x", pady=(6, 0))

        self.url_var = tk.StringVar()
        self.url_entry = tk.Entry(url_row, textvariable=self.url_var, font=(FONT, 11), bg="#F2F2F0", relief="flat", fg=TEXT, insertbackground=TEXT)
        self.url_entry.pack(side="left", fill="x", expand=True, ipady=8, ipadx=8)
        self.url_entry.bind("<Return>", lambda e: self._fetch_info())

        self.fetch_btn = tk.Button(url_row, text="Fetch", font=(FONT, 11, "bold"), bg=ACCENT, fg=BTN_FG, relief="flat", cursor="hand2", command=self._fetch_info, padx=16, pady=8)
        self.fetch_btn.pack(side="left", padx=(8, 0))

        tk.Frame(inner, bg=BORDER, height=1).pack(fill="x", pady=16)

        self.info_frame = tk.Frame(inner, bg=CARD_BG)
        self.info_frame.pack(fill="x")

        self.title_label = tk.Label(self.info_frame, text="", font=(FONT, 11, "bold"), bg=CARD_BG, fg=TEXT, wraplength=380, justify="left")
        self.dur_label = tk.Label(self.info_frame, text="", font=(FONT, 10), bg=CARD_BG, fg=SUBTEXT)

        self.dl_frame = tk.Frame(inner, bg=CARD_BG)

        tk.Label(self.dl_frame, text="Select Resolution", font=(FONT, 11, "bold"), bg=CARD_BG, fg=TEXT).pack(anchor="w", pady=(0, 6))

        self.quality_var = tk.StringVar()
        self.quality_menu = ttk.Combobox(self.dl_frame, textvariable=self.quality_var, state="readonly", font=(FONT, 11), width=18)
        self.quality_menu.pack(anchor="w")

        self.dl_btn = tk.Button(self.dl_frame, text="Download Video + Audio", font=(FONT, 12, "bold"), bg=ACCENT, fg=BTN_FG, relief="flat", cursor="hand2", command=self._start_download, padx=0, pady=10)
        self.dl_btn.pack(fill="x", pady=(14, 0))

        self.prog_frame = tk.Frame(wrap, bg=BG)
        self.prog_frame.pack(fill="x", pady=(16, 0))

        self.status_label = tk.Label(self.prog_frame, text="Ready", font=(FONT, 10), bg=BG, fg=SUBTEXT, wraplength=440, justify="left")
        self.status_label.pack(anchor="w")

        self.progress = ttk.Progressbar(self.prog_frame, length=448, mode="determinate")
        self.pct_label = tk.Label(self.prog_frame, text="", font=(FONT, 10), bg=BG, fg=SUBTEXT)

    def _fetch_info(self):
        url = self.url_var.get().strip()
        if not url:
            self._set_status("Please paste a valid video URL first.", ERROR)
            return

        self._set_status("Fetching video details...", SUBTEXT)
        self.fetch_btn.config(state="disabled")
        threading.Thread(target=self._do_fetch, args=(url,), daemon=True).start()

    def _do_fetch(self, url):
        try:
            ydl_opts = {'quiet': True, 'no_warnings': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            formats = info.get("formats", [])
            heights = set()
            for f in formats:
                if f.get("vcodec") != "none" and f.get("height"):
                    heights.add(f.get("height"))

            if not heights:
                self.after(0, lambda: self._set_status("No video streams found.", ERROR))
                self.after(0, lambda: self.fetch_btn.config(state="normal"))
                return

            sorted_res = [f"{h}p" for h in sorted(list(heights), reverse=True)]

            self._info = info
            self.after(0, lambda: self._show_info(info, sorted_res))

        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self._set_status(f"Error fetching video: {err_msg}", ERROR))
            self.after(0, lambda: self.fetch_btn.config(state="normal"))

    def _show_info(self, info, resolutions):
        title = info.get("title", "YouTube Video")
        duration_sec = info.get("duration", 0)
        mins, secs = divmod(duration_sec, 60)

        self.title_label.config(text=title)
        self.dur_label.config(text=f"Duration: {mins}:{secs:02d}")

        self.title_label.pack(anchor="w")
        self.dur_label.pack(anchor="w", pady=(2, 12))

        self.quality_menu.config(values=resolutions)
        self.quality_var.set(resolutions[0])

        self.dl_frame.pack(fill="x", pady=(4, 0), expand=True)
        self.fetch_btn.config(state="normal")
        self._set_status("Ready to download.", SUCCESS)
        self._fetched = True

    def _start_download(self):
        if not self._fetched or (self._dl_thread and self._dl_thread.is_alive()):
            return

        res = self.quality_var.get()
        self.dl_btn.config(state="disabled", text="Downloading...")
        self._dl_thread = threading.Thread(target=self._do_download, args=(res,), daemon=True)
        self._dl_thread.start()

    def _do_download(self, resolution_str):
        try:
            url = self.url_var.get().strip()
            height = resolution_str.replace("p", "")

            self.after(0, lambda: self._start_progress("Starting download..."))

            def progress_hook(d):
                if d["status"] == "downloading":
                    total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                    downloaded = d.get("downloaded_bytes", 0)
                    if total > 0:
                        pct = int((downloaded / total) * 100)
                        self.after(0, lambda p=pct: self._update_progress(p, f"Downloading ({p}%)..."))
                elif d["status"] == "finished":
                    self.after(0, lambda: self._update_progress(99, "Merging video & audio..."))

            ydl_opts = {
                'format': f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height}]+bestaudio/best',
                'outtmpl': os.path.join(DOWNLOAD_DIR, '%(title)s.%(ext)s'),
                'merge_output_format': 'mp4',
                'ffmpeg_location': get_resource_path('.'),
                'progress_hooks': [progress_hook],
                'quiet': True,
                'no_warnings': True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.after(0, lambda: self._update_progress(100, "Complete!"))
            self.after(0, lambda: self._set_status(f"Saved to Downloads folder (with audio)!", SUCCESS))

        except Exception as e:
            self.after(0, lambda err=str(e): self._set_status(f"Download Error: {err}", ERROR))

        finally:
            self.after(0, self._reset_btn)

    def _start_progress(self, msg):
        self.progress.pack(fill="x", pady=(6, 0))
        self.pct_label.pack(anchor="e")
        self._update_progress(0, msg)

    def _update_progress(self, pct, msg):
        self.progress["value"] = pct
        self.status_label.config(text=msg, fg=SUBTEXT)
        self.pct_label.config(text=f"{pct}%", fg=SUBTEXT)

    def _set_status(self, msg, color=SUBTEXT):
        self.status_label.config(text=msg, fg=color)

    def _reset_btn(self):
        self.dl_btn.config(state="normal", text="Download Video + Audio")

if __name__ == "__main__":
    app = VideoDownloaderApp()
    app.mainloop()