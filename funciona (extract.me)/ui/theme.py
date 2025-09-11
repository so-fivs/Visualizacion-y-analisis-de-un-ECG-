import tkinter as tk
from tkinter import ttk


PALETTE = {
    "bg": "#f0f0f0",
    "primary": "#1f77b4",
    "success": "#51cf66",
    "success_dark": "#40c057",
    "warning": "#ffd43b",
    "info": "#74c0fc",
    "accent": "#ff6b6b",
    "card": "#ffffff",
    "muted": "#6c757d",
    "elevated": "#f8f9fa",
}


def setup_theme(root: tk.Tk) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Base
    style.configure("TFrame", background=PALETTE["bg"])
    style.configure("TLabel", background=PALETTE["bg"], foreground="#222222")
    style.configure("TButton", padding=6)

    # Cards / containers
    style.configure("Card.TFrame", background=PALETTE["card"], relief="flat")
    style.configure("Section.TFrame", background=PALETTE["elevated"], relief="flat")

    # Text styles
    style.configure(
        "Header.TLabel",
        background=PALETTE["bg"],
        foreground=PALETTE["primary"],
        font=("Arial", 24, "bold"),
    )
    style.configure(
        "Title.TLabel",
        background=PALETTE["bg"],
        foreground="#111111",
        font=("Arial", 16, "bold"),
    )
    style.configure(
        "SubTitle.TLabel",
        background=PALETTE["bg"],
        foreground=PALETTE["muted"],
        font=("Arial", 12),
    )
    style.configure(
        "Emphasis.TLabel",
        background=PALETTE["bg"],
        foreground=PALETTE["accent"],
        font=("Arial", 36, "bold"),
    )
    style.configure(
        "Positive.TLabel",
        background=PALETTE["bg"],
        foreground=PALETTE["success"],
        font=("Arial", 12, "bold"),
    )

    # Icon buttons
    style.configure(
        "Icon.TButton",
        background=PALETTE["elevated"],
        foreground="#111111",
        font=("Arial", 14),
        relief="flat",
        borderwidth=0,
    )
    style.map(
        "Icon.TButton",
        background=[("active", "#e9ecef")],
    )

    # Themed sections
    style.configure("Risk.TFrame", background=PALETTE["success"])
    style.configure("RiskLevel.TLabel", background=PALETTE["success_dark"], foreground="white", font=("Arial", 14, "bold"))
    style.configure("Rec.TFrame", background=PALETTE["info"]) 
    style.configure("Factors.TFrame", background=PALETTE["warning"]) 
    style.configure(
    "Rounded.TButton",
    background=PALETTE["primary"],
    foreground="white",
    font=("Arial", 12, "bold"),
    borderwidth=0,
    relief="flat",
    padding=10,
)
    style.map(
    "Rounded.TButton",
    background=[("active", "#155a8a")],  # más oscuro al presionar
    )

    # Progressbar
    style.configure(
        "Progress.Horizontal.TProgressbar",
        troughcolor="#e9ecef",
        bordercolor="#e9ecef",
        lightcolor=PALETTE["success"],
        darkcolor=PALETTE["success"],
        background=PALETTE["success"],
        thickness=10,
    )

