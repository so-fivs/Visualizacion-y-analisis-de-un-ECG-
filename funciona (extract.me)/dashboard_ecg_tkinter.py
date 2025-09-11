from tkinter import ttk
import tkinter.messagebox as messagebox
import serial
import pandas as pd
import numpy as np
import tkinter as tk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Slider
import time
from datetime import datetime
import joblib
import platform
import os
import json

# Opcional: MQTT (wrap en try/except si no está instalado)
try:
    import paho.mqtt.client as mqtt
    MQTT_AVAILABLE = True
except Exception:
    MQTT_AVAILABLE = False

from ui.theme import setup_theme, PALETTE


class ECGDashboard:
    def __init__(self, root):
        self.root = root
        self.root.title("Electrocardiograma en tiempo real")
        self.root.geometry("1400x900")
        self.root.configure(bg=PALETTE['bg'])
        setup_theme(self.root)

        # ---------------- Datos del paciente (puedes cambiar dinámicamente) ----------------
        self.patient_data = {
            "edad": 68,
            "genero": "Masculino",
            "enfermedades": "hipertension, cardiopatia"
        }

        # ---------------- Datos ECG / análisis ----------------
        self.ecg_data = []
        self.xdata = []
        self.ydata = []
        self.sample_rate = 250  # Hz - ESP32-CAM

        self.r_peaks = []
        self.rr_intervals = []
        self.latest_rr_interval = 0.0
        self.heart_rate = 72
        self.heart_status = "NORMAL"
        self.status_color = "green"
        self.signal_quality = "EXCELENTE"

        # Control y estado
        self.serial_connected = False
        self.update_count = 0
        self.running = True

        # Cargar modelo de riesgo (joblib)
        self.risk_model = None
        try:
            self.risk_model = joblib.load("modelo_riesgo.pkl")
            print("✅ Modelo de riesgo cargado: modelo_riesgo.pkl")
        except Exception as e:
            self.risk_model = None
            print(f"⚠️ No se pudo cargar modelo_riesgo.pkl ({e}). Se usarán reglas base.")

        # Conexión serial (intenta conectar; si falla usa simulación)
        try:
            # Cambia "COM7" por tu puerto en mac/linux (ej. '/dev/ttyUSB0' o '/dev/tty.SLAB_USBtoUART')
            self.ser = serial.Serial("COM7", 115200, timeout=0.001)
            self.serial_connected = True
            print("✅ Conectado al puerto serial COM7")
        except Exception as e:
            self.ser = None
            self.serial_connected = False
            print(f"⚠️ No se pudo conectar al puerto serial COM7: {e}")
            print("📊 Usando datos simulados para demostración")

        # MQTT (opcional) - Configura el broker si lo deseas
        self.mqtt_client = None
        self.mqtt_topic = "ecg/paciente1"
        if MQTT_AVAILABLE:
            try:
                self.mqtt_client = mqtt.Client()
                # self.mqtt_client.username_pw_set(user, pwd)
                self.mqtt_client.connect("broker.emqx.io", 1883, 60)
                print("✅ MQTT broker conectado (broker.emqx.io:1883)")
            except Exception as e:
                print(f"⚠️ No se pudo conectar al broker MQTT: {e}")
                self.mqtt_client = None

        # Control de alertas (no spamear)
        self.last_alert_time = 0
        self.alert_cooldown = 10  # segundos mínimos entre alertas

        # Construir UI y start loop
        self.setup_ui()
        self.update_data()

    # ---------------- UI ----------------
    def setup_ui(self):
    # Frame principal
        main_frame = ttk.Frame(self.root, style='TFrame')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Header
        header_frame = ttk.Frame(main_frame, style='TFrame')
        header_frame.pack(fill='x', pady=(0, 20))

        # Título
        title_label = ttk.Label(header_frame, text="Electrocardiograma en tiempo real", style='Header.TLabel')
        title_label.pack(side='left')

        # Frame de iconos (derecha)
        icons_frame = ttk.Frame(header_frame, style='TFrame')
        icons_frame.pack(side='left')

        # Botón paciente (solo ícono)
        patient_btn = ttk.Button(icons_frame, text="🧑‍⚕️", style='Icon.TButton', command=self.open_patient_form, width=3)
        patient_btn.pack(side='left', padx=5)

        # Otros botones decorativos (sin llamar a funciones inexistentes)
        icon_emojis = ['⚙️', '⏱️', '📤']  # Configuración, historial, exportar
        for emoji in icon_emojis:
            btn = ttk.Button(icons_frame, text=emoji, style='Icon.TButton', width=3)
            btn.pack(side='left', padx=5)

        # Contenido principal
        content_frame = ttk.Frame(main_frame, style='TFrame')
        content_frame.pack(fill='both', expand=True)

        # Panel izquierdo (ECG y frecuencia cardiaca)
        left_frame = ttk.Frame(content_frame, style='TFrame')
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 100))
        self.create_heart_rate_panel(left_frame)
        self.create_ecg_panel(left_frame)

        # Panel derecho (riesgo, recomendaciones, factores)
        right_frame = ttk.Frame(content_frame, style='TFrame')
        right_frame.pack(side='left', fill='y', padx=(10, 0))
        self.create_risk_panel(right_frame)
        self.create_recommendation_panel(right_frame)
        self.create_factors_panel(right_frame)

    def open_patient_form(self):
        """Formulario sencillo para editar datos del paciente en runtime"""
        form = tk.Toplevel(self.root)
        form.title("Datos del Paciente")
        form.geometry("360x280")
        form.transient(self.root)
        form.configure(bg=PALETTE['bg'])

        style = ttk.Style()
        style.configure("Rounded.TEntry", padding=5, relief="flat", foreground="black", fieldbackground="white")
        style.configure("Rounded.TButton", relief="flat", background=PALETTE['primary'], foreground="white")
        style.map("Rounded.TButton", background=[('active', PALETTE['accent'])])

        # Edad
        ttk.Label(form, text="Edad:", background=PALETTE['bg']).pack(pady=(10, 0))
        age_entry = ttk.Entry(form, style="Rounded.TEntry")
        age_entry.insert(0, str(self.patient_data.get("edad", "")))
        age_entry.pack(pady=5, padx=20, fill='x')

        # Género
        ttk.Label(form, text="Género:", background=PALETTE['bg']).pack(pady=(10, 0))
        gender_var = tk.StringVar(value=self.patient_data.get("genero", "Masculino"))
        gender_menu = ttk.OptionMenu(form, gender_var, gender_var.get(), "Masculino", "Femenino", "Otro")
        gender_menu.pack(pady=5, padx=20, fill='x')

        # Enfermedades
        ttk.Label(form, text="Enfermedades:", background=PALETTE['bg']).pack(pady=(10, 0))
        diseases_entry = ttk.Entry(form, width=40, style="Rounded.TEntry")
        diseases_entry.insert(0, self.patient_data.get("enfermedades", ""))
        diseases_entry.pack(pady=5, padx=20, fill='x')

# Botón Guardar (estilo redondeado)
        ttk.Button(form, text="💾", style="Rounded.TButton", command=lambda: save_and_close()).pack(pady=15)


        # función interna para guardar y cerrar (anidada: tiene acceso a self y form)
        def save_and_close():
            try:
                edad = int(age_entry.get())
            except:
                edad = self.patient_data.get("edad", 30)

            self.patient_data["edad"] = edad
            self.patient_data["genero"] = gender_var.get()
            self.patient_data["enfermedades"] = diseases_entry.get()
            print("📋 Datos paciente actualizados:", self.patient_data)

            # 🚨 Evaluar riesgo inmediatamente con los datos guardados
            bpm_actual = getattr(self, "heart_rate", 72)
            rr_var = self.calculate_rr_variability() if hasattr(self, "rr_intervals") else 0

            # Si hay modelo cargado, construir un DataFrame con los mismos nombres de features
            if self.risk_model is not None:
                try:
                    X_df = pd.DataFrame([{
                        "edad": edad,
                        "bpm": bpm_actual,
                        "rr_var": rr_var,
                        "hipertension": 1 if "hipertension" in self.patient_data.get("enfermedades", "").lower() else 0,
                        "cardiopatia": 1 if "cardiopatia" in self.patient_data.get("enfermedades", "").lower() else 0
                    }])
                    # usar predict_proba sobre DataFrame — evita el warning de feature names
                    prob = float(self.risk_model.predict_proba(X_df)[0][1]) * 100
                    riesgo = {"nivel": "BAJO", "probabilidad": int(prob), "mensaje": f"Probabilidad {prob:.0f}%"}
                    if prob > 70:
                        riesgo["nivel"] = "ALTO"
                    elif prob > 40:
                        riesgo["nivel"] = "MODERADO"
                except Exception as e:
                    print("⚠️ Error usando modelo de riesgo al guardar:", e)
                    riesgo = self.evaluate_risk(bpm_actual, rr_var)
            else:
                riesgo = self.evaluate_risk(bpm_actual, rr_var)

            self.update_risk_ui(riesgo)

            form.destroy()

        # botón dentro de la función (correcto scope)
        ttk.Button(form, text="Guardar", command=save_and_close).pack(pady=15)

    # ---------------- Panels (sin cambios relevantes) ----------------
    def create_heart_rate_panel(self, parent):
        hr_frame = ttk.Frame(parent, style='Card.TFrame')
        hr_frame.pack(fill='x', pady=(0, 20))
        content_frame = ttk.Frame(hr_frame, style='Card.TFrame')
        content_frame.pack(fill='both', padx=20, pady=20)

        left_side = ttk.Frame(content_frame, style='Card.TFrame')
        left_side.pack(side='left')

        heart_label = ttk.Label(left_side, text="❤️", font=('Arial', 36))
        heart_label.pack(side='left')

        bpm_frame = ttk.Frame(left_side, style='Card.TFrame')
        bpm_frame.pack(side='left', padx=(20, 0))

        self.bpm_label = ttk.Label(bpm_frame, text="71 BPM", style='Emphasis.TLabel')
        self.bpm_label.pack()

        self.status_label = ttk.Label(bpm_frame, text="● Normal", style='Positive.TLabel')
        self.status_label.pack()

        right_side = ttk.Frame(content_frame, style='Card.TFrame')
        right_side.pack(side='right')

        rhythm_label = ttk.Label(right_side, text="Ritmo", style='SubTitle.TLabel')
        rhythm_label.pack(anchor='e')

        sinusal_label = ttk.Label(right_side, text="Sinusal", style='TLabel')
        sinusal_label.pack(anchor='e')

        self.time_label = ttk.Label(right_side, text="", font=('Arial', 10))
        self.time_label.pack(anchor='e')

    def create_ecg_panel(self, parent):
        ecg_frame = ttk.Frame(parent, style='Section.TFrame')
        ecg_frame.pack(fill='both', expand=True)
        info_frame = ttk.Frame(ecg_frame, style='Section.TFrame')
        info_frame.pack(fill='x', padx=10, pady=10)

        info_left = ttk.Frame(info_frame, style='Section.TFrame')
        info_left.pack(side='left')
        for info in ["ECG Lead II", "Velocidad: 25mm/s", "Amplitud: 10mm/mV"]:
            info_label = ttk.Label(info_left, text=info, font=('Arial', 10))
            info_label.pack(anchor='w')

        live_frame = ttk.Frame(info_frame, style='Section.TFrame')
        live_frame.pack(side='right')
        live_label = ttk.Label(live_frame, text="● LIVE", foreground=PALETTE['success'], font=('Arial', 12, 'bold'))
        live_label.pack()

        self.fig, self.ax = plt.subplots(figsize=(12, 8))
        self.xdata, self.ydata = [], []
        self.offset_value = 0
        self.line, = self.ax.plot([], [], lw=2)

        self.ax.set_xlim(0, 5)
        self.ax.set_ylim(-3000, 3000)
        self.ax.set_title('Monitor de Señal Cardíaca', fontsize=16)
        self.ax.set_xlabel('Tiempo (s)', fontsize=12)
        self.ax.set_ylabel('Amplitud (mV)', fontsize=12)
        self.ax.grid(True, alpha=0.3)
        self.ax.axhline(y=0, color='gray', linestyle='-', alpha=0.5)

        ax_offset = plt.axes([0.25, 0.02, 0.5, 0.03])
        self.offset_slider = Slider(ax=ax_offset, label='Offset (mV)', valmin=-2000, valmax=2000, valinit=0, valfmt='%+d mV')
        self.offset_slider.on_changed(self.offset_update)

        self.canvas = FigureCanvasTkAgg(self.fig, ecg_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill='both', expand=True, padx=10, pady=10)

        self.ani = FuncAnimation(self.fig, self.update_animation, init_func=self.init_animation, blit=True, interval=5, cache_frame_data=False)

    def create_risk_panel(self, parent):
        risk_frame = ttk.Frame(parent, style='Risk.TFrame')
        risk_frame.pack(fill='x', pady=(0, 15))
        content_frame = ttk.Frame(risk_frame, style='Risk.TFrame')
        content_frame.pack(fill='both', padx=20, pady=20)

        title_frame = ttk.Frame(content_frame, style='Risk.TFrame')
        title_frame.pack(fill='x', pady=(0, 15))

        shield_label = ttk.Label(title_frame, text="🛡️", font=('Arial', 24), foreground='white', background=PALETTE['success'])
        shield_label.pack(side='left')

        risk_title = ttk.Label(title_frame, text="Riesgo de Arritmia", font=('Arial', 16, 'bold'), foreground='white', background=PALETTE['success'])
        risk_title.pack(side='left', padx=(10, 0))

        self.risk_level_label = ttk.Label(content_frame, text="BAJO", style='RiskLevel.TLabel')
        self.risk_level_label.pack(pady=10)

        self.risk_score_label = ttk.Label(content_frame, text="0%", font=('Arial', 18, 'bold'), foreground='white', background=PALETTE['success'])
        self.risk_score_label.pack()

        self.risk_message_label = ttk.Label(content_frame, text="Ritmo cardíaco normal", font=('Arial', 12), foreground='white', background=PALETTE['success'])
        self.risk_message_label.pack()

    def create_recommendation_panel(self, parent):
        rec_frame = ttk.Frame(parent, style='Rec.TFrame')
        rec_frame.pack(fill='x', pady=(0, 15))
        content_frame = ttk.Frame(rec_frame, style='Rec.TFrame')
        content_frame.pack(fill='both', padx=20, pady=20)

        rec_title = ttk.Label(content_frame, text="Recomendación", font=('Arial', 16, 'bold'), foreground='white', background=PALETTE['info'])
        rec_title.pack()

        self.rec_text = ttk.Label(content_frame, text="Continuar monitoreo rutinario", font=('Arial', 12), foreground='white', background=PALETTE['info'], wraplength=200)
        self.rec_text.pack(pady=10)

    def create_factors_panel(self, parent):
        factors_frame = ttk.Frame(parent, style='Factors.TFrame')
        factors_frame.pack(fill='x')
        content_frame = ttk.Frame(factors_frame, style='Factors.TFrame')
        content_frame.pack(fill='both', padx=20, pady=20)

        factors_title = ttk.Label(content_frame, text="Factores Evaluados", font=('Arial', 16, 'bold'), foreground='white', background=PALETTE['warning'])
        factors_title.pack()

        self.factor_labels = {}
        factors_info = [
            ("Frecuencia cardíaca:", "heart_rate"),
            ("RR Interval:", "rr_interval"),
            ("Estado cardíaco:", "heart_status"),
            ("Calidad de señal:", "signal_quality"),
            ("Variabilidad R-R:", "rr_variability")
        ]

        for factor_name, factor_key in factors_info:
            factor_frame = ttk.Frame(content_frame, style='Factors.TFrame')
            factor_frame.pack(fill='x', pady=5)

            factor_label = ttk.Label(factor_frame, text=factor_name, font=('Arial', 12, 'bold'), foreground='white', background=PALETTE['warning'])
            factor_label.pack(side='left')

            value_label = ttk.Label(factor_frame, text="--", font=('Arial', 12, 'bold'), foreground=PALETTE['success'], background=PALETTE['warning'])
            value_label.pack(side='right')

            self.factor_labels[factor_key] = value_label

    # ---------------- Rest of methods unchanged (offset_update, animation, detection, etc.) ----------------
    def offset_update(self, val):
        self.offset_value = int(val)
        if len(self.ydata) > 0:
            ydata_offset = [y + self.offset_value for y in self.ydata]
            self.line.set_data(self.xdata, ydata_offset)

    def init_animation(self):
        self.ax.set_xlim(0, 5)
        self.ax.set_ylim(-3000, 3000)
        return self.line,

    def update_animation(self, frame):
        # Leer puerto serial si está conectado
        while self.ser and self.ser.in_waiting > 0:
            try:
                line_data = self.ser.readline()
                if line_data:
                    value = int(line_data.decode().strip())
                    signal_value = (value - 2048) * 1.5
                    if len(self.ydata) > 0:
                        signal_value = 0.8 * signal_value + 0.2 * self.ydata[-1]
                    self.ydata.append(signal_value)
                    time_seconds = len(self.xdata) / self.sample_rate
                    self.xdata.append(time_seconds)
                    ydata_offset = [y + self.offset_value for y in self.ydata]
                    self.line.set_data(self.xdata, ydata_offset)
                    current_time = self.xdata[-1]
                    if current_time > 5:
                        self.ax.set_xlim(current_time - 5, current_time)
                    else:
                        self.ax.set_xlim(0, 5)
                    if len(self.ydata) % 250 == 0 and len(self.ydata) > 100:
                        self.calculate_and_update_bpm_direct()
            except Exception:
                break

        # Si no hay serial, generar datos sintéticos
        if not self.serial_connected:
            new_data = self.generate_synthetic_data()
            self.ydata.append(new_data)
            time_seconds = len(self.xdata) / self.sample_rate
            self.xdata.append(time_seconds)
            ydata_offset = [y + self.offset_value for y in self.ydata]
            self.line.set_data(self.xdata, ydata_offset)
            current_time = self.xdata[-1]
            if current_time > 5:
                self.ax.set_xlim(current_time - 5, current_time)
            else:
                self.ax.set_xlim(0, 5)
            if len(self.ydata) % 250 == 0 and len(self.ydata) > 100:
                self.calculate_and_update_bpm_direct()

        return self.line,

    def detect_r_peaks(self, signal_data, time_data):
        if len(signal_data) < 100:
            return [], []
        threshold = np.mean(signal_data) + 1.0 * np.std(signal_data)
        peaks = []
        min_distance = int(0.3 * self.sample_rate)
        for i in range(5, len(signal_data)-5):
            if (signal_data[i] > threshold and
                signal_data[i] > signal_data[i-1] and
                signal_data[i] > signal_data[i-2] and
                signal_data[i] > signal_data[i+1] and
                signal_data[i] > signal_data[i+2]):
                if len(peaks) == 0 or (i - peaks[-1]) >= min_distance:
                    peaks.append(i)
        peak_times = [time_data[i] for i in peaks if i < len(time_data)]
        peak_values = [signal_data[i] for i in peaks if i < len(signal_data)]
        return peak_times, peak_values

    def calculate_rr_variability(self):
        """Calcula la variabilidad de RR en porcentaje"""
        if len(self.rr_intervals) < 3:
            return 0
        mean_rr = np.mean(self.rr_intervals)
        std_rr = np.std(self.rr_intervals)
        if mean_rr == 0:
            return 0
        return (std_rr / mean_rr) * 100

    def calculate_and_update_bpm_direct(self):
        """Calcular BPM aproximado usando detección simple de picos"""
        try:
            if len(self.ydata) < 100:
                self.use_simulated_bpm()
                return
            self.heart_rate = self.calculate_heart_rate_simple(self.ydata)
            if self.heart_rate == 72:
                self.use_simulated_bpm()
            self.heart_status, self.status_color = self.evaluate_heart_status(
                self.heart_rate,
                self.calculate_rr_variability()
            )
            self._update_ui_direct()
        except Exception as e:
            print("Error calculate_and_update_bpm_direct:", e)
            self.use_simulated_bpm()

    def evaluate_heart_status(self, bpm, rr_variability):
        if bpm > 140:
            return "URGENTE", "red"
        if bpm > 100:
            return "TAQUICARDIA", "red"
        if bpm < 50:
            return "BRADICARDIA", "yellow"
        if 50 <= bpm <= 100:
            if rr_variability > 20:
                return "ARRITMIA", "red"
            return "NORMAL", "green"
        return "NORMAL", "green"

    def evaluate_risk(self, bpm, rr_variability):
        """Usa modelo cargado si existe; si no, usa heurística simple"""
        edad = self.patient_data.get("edad", 30)
        enfermedades = self.patient_data.get("enfermedades", "").lower()
        hipertension = 1 if "hipertension" in enfermedades else 0
        cardiopatia = 1 if "cardiopatia" in enfermedades else 0

        # Si hay modelo, usarlo
        if self.risk_model is not None:
            try:
                # crear DataFrame con nombres de columnas consistentes con el entrenamiento
                X_df = pd.DataFrame([{
                    "edad": edad,
                    "bpm": bpm,
                    "rr_var": rr_variability,
                    "hipertension": hipertension,
                    "cardiopatia": cardiopatia
                }])
                prob = float(self.risk_model.predict_proba(X_df)[0][1]) * 100
                if prob > 70:
                    nivel = "ALTO"
                elif prob > 40:
                    nivel = "MODERADO"
                else:
                    nivel = "BAJO"
                mensaje = f"Probabilidad {prob:.0f}%"
                return {"nivel": nivel, "probabilidad": int(prob), "mensaje": mensaje}
            except Exception as e:
                print("⚠️ Error usando modelo de riesgo:", e)
                # caerá a heurística

        # Heurística fallback
        riesgo = {"nivel": "BAJO", "probabilidad": 5, "mensaje": "Ritmo normal"}
        if edad > 65 and bpm > 110:
            riesgo = {"nivel": "ALTO", "probabilidad": 70, "mensaje": "Taquicardia en adulto mayor"}
        if "hipertension" in enfermedades and bpm < 45:
            riesgo = {"nivel": "MODERADO", "probabilidad": 50, "mensaje": "Bradicardia con HTA"}

        # ✅ calcular rr_variabilidad normal
        rr_variabilidad = rr_variability  
        if "cardiopatia" in enfermedades and rr_variabilidad > 30:
            riesgo = {"nivel": "ALTO", "probabilidad": 80, "mensaje": "Riesgo de arritmia ventricular"}

        return riesgo

    def show_toast_alert(self, mensaje, nivel="ALTO", duracion=3000):
        """
        Muestra alerta tipo 'toast' centrada y con colores pastel, sin errores en macOS.
        """
        colors = {
        "BAJO": "#4caf50",       # verde
        "MODERADO": "#ff9800",   # naranja
        "ALTO": "#f44336"        # rojo
        }
        bg_color = colors.get(nivel, "#f44336")

        # Crear Toplevel
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True)
        toast.transient(self.root)        # Hace que dependa de la ventana principal
        toast.lift()                      # Traer al frente
        toast.attributes("-topmost", True)
        
        width, height = 300, 100

        # Posición centrada
        self.root.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - width // 2
        y = self.root.winfo_y() + (self.root.winfo_height() // 2) - height // 2
        toast.geometry(f"{width}x{height}+{x}+{y}")

        # Frame redondeado
        frame = tk.Frame(toast, bg=bg_color, bd=2, relief="ridge")
        frame.place(relwidth=1, relheight=1)

        # Texto
        label = tk.Label(frame, text=mensaje, bg=bg_color, fg="white",
                        font=("Arial", 12, "bold"), wraplength=width-20)
        label.pack(expand=True, padx=10, pady=10)

        # Animación fade in/out simple
        def fade(count=0, step=0.05, fade_in=True):
            alpha = count * step
            if not fade_in:
                alpha = 1 - alpha
            toast.attributes("-alpha", alpha)
            if count < int(1/step):
                self.root.after(20, lambda: fade(count+1, step, fade_in))
            else:
                if fade_in:
                    self.root.after(duracion, lambda: fade(0, step, fade_in=False))
                else:
                    toast.destroy()

        fade()


    def update_risk_ui(self, riesgo):
        """Actualizar panel de riesgo clínico, mostrar alerta y log en consola"""
        # Actualizar UI
        self.risk_level_label.config(text=riesgo["nivel"])
        self.risk_score_label.config(text=f"{riesgo['probabilidad']}%")
        self.risk_message_label.config(text=riesgo["mensaje"])

        # Mensaje de recomendación según nivel de riesgo
        if riesgo["nivel"] == "ALTO":
            self.rec_text.config(text="ALERTA: Evaluar al paciente y considerar intervención urgente")
        elif riesgo["nivel"] == "MODERADO":
            self.rec_text.config(text="Monitorear y consultar con especialista")
        else:
            self.rec_text.config(text="Continuar monitoreo rutinario")

        # ---------------- Mostrar alerta tipo toast para cualquier nivel ----------------
        now = time.time()
        if (now - self.last_alert_time) > self.alert_cooldown:
            self.last_alert_time = now
            alert_msg = f"Riesgo: {riesgo['nivel']} | Probabilidad: {riesgo['probabilidad']}% | {riesgo['mensaje']}"
            self.show_toast_alert(alert_msg, nivel=riesgo['nivel'], duracion=4000)

        # ---------------- Log en consola ----------------
        print(f"📊 ALERTA RIESGO PACIENTE: {riesgo['nivel']} | Probabilidad: {riesgo['probabilidad']}% | Mensaje: {riesgo['mensaje']}")

        # Enviar datos a MQTT
        self.send_data_mqtt(self.heart_rate, riesgo)

        

        # ---------------- Mostrar alerta si es ALTO ----------------
        now = time.time()
        if riesgo["nivel"] == "ALTO" and (now - self.last_alert_time) > self.alert_cooldown:
            self.last_alert_time = now
            self.show_alert_popup_and_sound(riesgo)

        # ---------------- Log en consola ----------------
        print(f"📊 ALERTA RIESGO PACIENTE: {riesgo['nivel']} | Probabilidad: {riesgo['probabilidad']}% | Mensaje: {riesgo['mensaje']}")

        # Enviar datos a MQTT
        self.send_data_mqtt(self.heart_rate, riesgo)

    def show_alert_popup_and_sound(self, riesgo):
        try:
            # Mensaje flotante en la UI
            alert_msg = f"ALERTA PACIENTE: {riesgo['nivel']} | Probabilidad: {riesgo['probabilidad']}% | {riesgo['mensaje']}"
            self.show_toast_alert(alert_msg, riesgo['nivel'], duracion=5000)

            # Sonido opcional
            os_name = platform.system()
            try:
                if os_name == "Windows":
                    import winsound
                    winsound.Beep(1000, 800)
                elif os_name == "Darwin":
                    os.system("afplay /System/Library/Sounds/Glass.aiff")
                else:
                    if os.system("paplay /usr/share/sounds/freedesktop/stereo/complete.oga") != 0:
                        if os.system("aplay /usr/share/sounds/alsa/Front_Center.wav") != 0:
                            print("\a")
            except Exception as e:
                print("⚠️ No se pudo reproducir sonido de alerta:", e)

        except Exception as e:
            print("⚠️ Error mostrando alerta:", e)


    def send_data_mqtt(self, bpm, riesgo):
        if self.mqtt_client is None:
            return
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "paciente": self.patient_data,
            "bpm": bpm,
            "riesgo": riesgo
        }
        try:
            self.mqtt_client.publish(self.mqtt_topic, json.dumps(payload))
        except Exception as e:
            print("⚠️ Error publicando MQTT:", e)

    def update_ui_from_animation(self):
        try:
            self.root.after(0, self._update_ui_safe)
        except Exception:
            pass

    def _update_ui_safe(self):
        try:
            if hasattr(self, 'bpm_label'):
                self.bpm_label.config(text=f"{self.heart_rate} BPM")
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"● {self.heart_status}")
            if hasattr(self, 'time_label'):
                self.time_label.config(text=datetime.now().strftime('%I:%M:%S %p'))

            if hasattr(self, 'factor_labels') and self.factor_labels:
                self.factor_labels['heart_rate'].config(text=f"{self.heart_rate} BPM")
                self.factor_labels['rr_interval'].config(text=f"{getattr(self, 'latest_rr_interval', 0):.3f}s")
                self.factor_labels['heart_status'].config(text=self.heart_status)
                self.factor_labels['signal_quality'].config(text=self.signal_quality)
                self.factor_labels['rr_variability'].config(text=f"{self.calculate_rr_variability():.1f}%")
        except Exception as e:
            print("Error actualizando UI:", e)

    def generate_synthetic_data(self):
        t = time.time()
        base_signal = 1000 * np.sin(2 * np.pi * 1.2 * t)  # ~72 BPM
        noise = np.random.normal(0, 100)
        return base_signal + noise

    def update_data(self):
        try:
            if not self.root.winfo_exists():
                return
        except:
            return

        if self.update_count % 100 == 0 and len(self.ydata) > 50:
            self.signal_quality = self.evaluate_signal_quality(self.ydata[-100:])

        if self.update_count % 20 == 0 and len(self.ydata) > 100:
            self.calculate_and_update_bpm_direct()

        self.update_count += 1

        if self.running:
            self.root.after(100, self._update_callback)

    def _update_callback(self):
        if self.running:
            self.update_data()
    # Agregar estos métodos dentro de la clase ECGDashboar


    def calculate_heart_rate_simple(self, signal_data):
        if len(signal_data) < 100:
            return 72
        threshold = np.mean(signal_data) + 0.5 * np.std(signal_data)
        peaks = []
        for i in range(2, len(signal_data)-2):
            if (signal_data[i] > threshold and
                signal_data[i] > signal_data[i-1] and
                signal_data[i] > signal_data[i-2] and
                signal_data[i] > signal_data[i+1] and
                signal_data[i] > signal_data[i+2]):
                peaks.append(i)
        if len(peaks) > 1:
            intervals = np.diff(peaks)
            if len(intervals) > 0:
                avg_interval = np.mean(intervals)
                bpm = int(60 * self.sample_rate / max(1, avg_interval))
                return max(30, min(220, bpm))
        return 72

    def use_simulated_bpm(self):
        self.heart_rate = 72
        self.heart_status = "NORMAL"
        self.status_color = "green"
        self._update_ui_direct()

    def _update_ui_direct(self):
        try:
            if hasattr(self, 'bpm_label'):
                self.bpm_label.config(text=f"{self.heart_rate} BPM")
            if hasattr(self, 'status_label'):
                self.status_label.config(text=f"● {self.heart_status}")
            if hasattr(self, 'factor_labels') and self.factor_labels:
                self.factor_labels['heart_rate'].config(text=f"{self.heart_rate} BPM")
                self.factor_labels['rr_interval'].config(text=f"{getattr(self, 'latest_rr_interval', 0):.3f}s")
                self.factor_labels['heart_status'].config(text=self.heart_status)
                self.factor_labels['signal_quality'].config(text=self.signal_quality)
                self.factor_labels['rr_variability'].config(text=f"{self.calculate_rr_variability():.1f}%")
        except Exception as e:
            print("Error _update_ui_direct:", e)

    def evaluate_signal_quality(self, signal_data):
        if len(signal_data) < 10:
            return "REGULAR"
        signal_std = np.std(signal_data)
        if signal_std > 100:
            return "EXCELENTE"
        elif signal_std > 50:
            return "BUENA"
        else:
            return "REGULAR"

    def cleanup(self):
        self.running = False
        if self.serial_connected and self.ser:
            try:
                self.ser.close()
            except:
                pass
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
            except:
                pass


def main():
    root = tk.Tk()
    app = ECGDashboard(root)

    def on_closing():
        app.cleanup()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
