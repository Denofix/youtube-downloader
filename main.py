import os
import sys
import threading
from io import BytesIO
import requests
import yt_dlp
from PIL import Image
import customtkinter as ctk
from tkinter import messagebox

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def app_folder():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

DOWNLOAD_FOLDER = os.path.join(app_folder(), "Youtube downloaders")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

def get_ffmpeg_path():
    ffmpeg_path = resource_path("ffmpeg.exe")
    if os.path.exists(ffmpeg_path):
        return ffmpeg_path
    return None

def open_downloads_folder():
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    os.startfile(DOWNLOAD_FOLDER)

def paste_link():
    try:
        url_entry.delete(0, "end")
        url_entry.insert(0, app.clipboard_get())
    except:
        messagebox.showerror("Ошибка", "Буфер обмена пустой")

def update_quality_visibility():
    if format_var.get() == "mp4":
        quality_label.grid(row=1, column=0, padx=(0, 10), pady=(10, 0), sticky="w")
        quality_box.grid(row=1, column=1, padx=(0, 0), pady=(10, 0), sticky="w")
    else:
        quality_label.grid_forget()
        quality_box.grid_forget()

def load_preview():
    threading.Thread(target=load_preview_thread, daemon=True).start()

def load_preview_thread():
    url = url_entry.get().strip()
    if not url:
        app.after(0, lambda: messagebox.showerror("Ошибка", "Вставь ссылку"))
        return
    try:
        app.after(0, lambda: preview_title.configure(text="Загрузка информации..."))
        options = {
            "quiet": True,
            "skip_download": True,
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=False)
        video_title = info.get("title", "Без названия")
        thumbnail_url = info.get("thumbnail")
        app.after(0, lambda: preview_title.configure(text=video_title))

        if thumbnail_url:
            response = requests.get(thumbnail_url, timeout=10)
            image = Image.open(BytesIO(response.content))
            image = image.resize((240, 135))
            preview_image = ctk.CTkImage(
                light_image=image,
                dark_image=image,
                size=(240, 135)
            )

            def set_image():
                thumbnail_label.configure(image=preview_image, text="")
                thumbnail_label.image = preview_image
            app.after(0, set_image)

    except Exception as e:
        app.after(0, lambda: preview_title.configure(text="Не удалось загрузить превью"))
        app.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

def download():
    threading.Thread(target=download_thread, daemon=True).start()

def download_thread():
    url = url_entry.get().strip()
    file_format = format_var.get()
    if not url:
        app.after(0, lambda: messagebox.showerror("Ошибка", "Вставь ссылку"))
        return
    os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
    ffmpeg_path = get_ffmpeg_path()
    if ffmpeg_path is None:
        app.after(
            0,
            lambda: messagebox.showerror(
                "Ошибка FFmpeg",
                "FFmpeg не найден.\n\n"
                "Положи файл ffmpeg.exe рядом с программой."
            )
        )
        return

    try:
        app.after(0, lambda: status_label.configure(text="Скачивание...", text_color="#facc15"))
        app.after(0, lambda: download_button.configure(state="disabled", text="Скачивание..."))
        if file_format == "mp3":
            options = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
                "ffmpeg_location": ffmpeg_path,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }
        else:
            quality = quality_var.get().replace("p", "")
            options = {
                "format": (
                    f"bestvideo[ext=mp4][height<={quality}]+bestaudio[ext=m4a]/"
                    f"best[ext=mp4][height<={quality}]/"
                    f"best"
                ),

                "outtmpl": os.path.join(DOWNLOAD_FOLDER, "%(title)s.%(ext)s"),
                "ffmpeg_location": ffmpeg_path,
                "merge_output_format": "mp4",
                "postprocessors": [{
                    "key": "FFmpegVideoConvertor",
                    "preferedformat": "mp4",
                }],
            }
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.download([url])

        app.after(
            0,
            lambda: status_label.configure(
                text="Готово! Файл сохранён в Youtube downloaders",
                text_color="#22c55e"
            )
        )
        app.after(0, lambda: messagebox.showinfo("Готово", "Файл успешно скачан!"))

    except Exception as e:
        app.after(0, lambda: status_label.configure(text="Ошибка скачивания", text_color="#ef4444"))
        app.after(0, lambda: messagebox.showerror("Ошибка", str(e)))

    finally:
        app.after(0, lambda: download_button.configure(state="normal", text="⬇ Скачать"))

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

app = ctk.CTk()
app.title("YouTube Downloader")
app.geometry("680x710")
app.resizable(False, False)
app.configure(fg_color="#0f172a")

try:
    app.iconbitmap(resource_path("icon.ico"))
except:
    pass

title_label = ctk.CTkLabel(
    app,
    text="YouTube Downloader",
    font=("Arial", 31, "bold"),
    text_color="white"
)
title_label.pack(pady=(18, 2))

subtitle_label = ctk.CTkLabel(
    app,
    text="Скачивание видео в MP3 или MP4",
    font=("Arial", 15),
    text_color="#94a3b8"
)
subtitle_label.pack(pady=(0, 4))

author_label = ctk.CTkLabel(
    app,
    text="Created by Nord_Fillin | Version 1.0",
    font=("Arial", 12),
    text_color="#64748b"
)
author_label.pack(pady=(0, 10))

main_frame = ctk.CTkFrame(
    app,
    fg_color="#1e293b",
    corner_radius=14,
    height=225
)
main_frame.pack(padx=30, pady=(0, 8), fill="x")
main_frame.pack_propagate(False)

url_label = ctk.CTkLabel(
    main_frame,
    text="Ссылка на видео:",
    font=("Arial", 15, "bold"),
    text_color="white"
)
url_label.pack(anchor="w", padx=22, pady=(16, 6))

url_entry = ctk.CTkEntry(
    main_frame,
    width=600,
    height=40,
    corner_radius=10,
    fg_color="#334155",
    border_color="#3b82f6",
    border_width=1,
    text_color="white",
    placeholder_text="Вставь ссылку на YouTube...",
    placeholder_text_color="#94a3b8",
    font=("Arial", 14)
)
url_entry.pack(padx=22, pady=(0, 12))

url_entry.bind("<Control-v>", lambda event: paste_link())
url_entry.bind("<Control-V>", lambda event: paste_link())
url_entry.bind("<Shift-Insert>", lambda event: paste_link())

controls_frame = ctk.CTkFrame(
    main_frame,
    fg_color="transparent"
)
controls_frame.pack(anchor="w", padx=22, pady=(0, 0))

paste_button = ctk.CTkButton(
    controls_frame,
    text="Вставить ссылку",
    command=paste_link,
    width=150,
    height=38,
    corner_radius=12,
    fg_color="#475569",
    hover_color="#64748b",
    font=("Arial", 13, "bold")
)
paste_button.grid(row=0, column=0, padx=(0, 8))

preview_button = ctk.CTkButton(
    controls_frame,
    text="Показать превью",
    command=load_preview,
    width=155,
    height=38,
    corner_radius=12,
    fg_color="#4f46e5",
    hover_color="#4338ca",
    font=("Arial", 13, "bold")
)
preview_button.grid(row=0, column=1, padx=(0, 28))

format_var = ctk.StringVar(value="mp3")

mp3_radio = ctk.CTkRadioButton(
    controls_frame,
    text="MP3",
    variable=format_var,
    value="mp3",
    command=update_quality_visibility,
    font=("Arial", 15, "bold"),
    text_color="white",
    fg_color="#3b82f6",
    hover_color="#2563eb"
)
mp3_radio.grid(row=0, column=2, padx=(0, 18))

mp4_radio = ctk.CTkRadioButton(
    controls_frame,
    text="MP4",
    variable=format_var,
    value="mp4",
    command=update_quality_visibility,
    font=("Arial", 15, "bold"),
    text_color="white",
    fg_color="#3b82f6",
    hover_color="#2563eb"
)
mp4_radio.grid(row=0, column=3)

quality_frame = ctk.CTkFrame(
    main_frame,
    fg_color="transparent"
)
quality_frame.pack(anchor="w", padx=22, pady=(8, 0))
quality_var = ctk.StringVar(value="720p")

quality_label = ctk.CTkLabel(
    quality_frame,
    text="Качество MP4:",
    font=("Arial", 14, "bold"),
    text_color="white"
)

quality_box = ctk.CTkComboBox(
    quality_frame,
    variable=quality_var,
    values=["360p", "480p", "720p", "1080p"],
    width=140,
    height=34,
    corner_radius=10,
    fg_color="#334155",
    border_color="#3b82f6",
    button_color="#2563eb",
    button_hover_color="#1d4ed8",
    dropdown_fg_color="#1e293b",
    dropdown_hover_color="#334155",
    font=("Arial", 13)
)

preview_frame = ctk.CTkFrame(
    app,
    fg_color="#0f172a",
    corner_radius=0
)
preview_frame.pack(pady=(2, 4))

thumbnail_label = ctk.CTkLabel(
    preview_frame,
    text="",
    width=240,
    height=135,
    fg_color="#020617",
    corner_radius=12
)
thumbnail_label.pack(pady=(0, 5))

preview_title = ctk.CTkLabel(
    preview_frame,
    text="Название видео появится здесь",
    width=600,
    wraplength=570,
    justify="center",
    font=("Arial", 13, "bold"),
    text_color="white"
)
preview_title.pack(pady=(0, 4))

download_button = ctk.CTkButton(
    app,
    text="⬇ Скачать",
    command=download,
    width=360,
    height=54,
    corner_radius=14,
    fg_color="#2563eb",
    hover_color="#1d4ed8",
    font=("Arial", 22, "bold")
)
download_button.pack(pady=(4, 8))

folder_button = ctk.CTkButton(
    app,
    text="Открыть папку загрузок",
    command=open_downloads_folder,
    width=310,
    height=44,
    corner_radius=12,
    fg_color="#16a34a",
    hover_color="#15803d",
    font=("Arial", 16, "bold")
)
folder_button.pack(pady=(0, 5))

status_label = ctk.CTkLabel(
    app,
    text="Ожидание ссылки...",
    font=("Arial", 12),
    text_color="#94a3b8"
)
status_label.pack(pady=(0, 5))
update_quality_visibility()
app.mainloop()