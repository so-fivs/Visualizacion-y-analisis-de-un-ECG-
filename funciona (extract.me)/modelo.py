# entrenar_modelo.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
import joblib

# Generar dataset sintético con 200 pacientes
np.random.seed(42)
n = 200

data = pd.DataFrame({
    "edad": np.random.randint(20, 90, n),  # edades entre 20 y 90
    "bpm": np.random.randint(40, 160, n),  # frecuencia cardíaca entre 40 y 160
    "rr_var": np.random.randint(5, 50, n), # variabilidad RR en ms
    "hipertension": np.random.choice([0, 1], n, p=[0.6, 0.4]),  # 40% con hipertensión
    "cardiopatia": np.random.choice([0, 1], n, p=[0.7, 0.3])    # 30% con cardiopatía
})

# Etiqueta de riesgo (heurística básica para entrenar)
def calcular_riesgo(row):
    riesgo = 0
    if row["edad"] > 65 and row["bpm"] > 110:
        riesgo = 1
    if row["bpm"] < 45:
        riesgo = 1
    if row["cardiopatia"] == 1 and row["rr_var"] > 25:
        riesgo = 1
    return riesgo

data["riesgo_alto"] = data.apply(calcular_riesgo, axis=1)

# Separar features y etiquetas
X = data.drop("riesgo_alto", axis=1)
y = data["riesgo_alto"]

# Entrenar modelo Random Forest
model = RandomForestClassifier(n_estimators=200, random_state=42)
model.fit(X, y)

# Guardar modelo entrenado
joblib.dump(model, "modelo_riesgo.pkl")
print("✅ Modelo guardado en modelo_riesgo.pkl con", len(data), "ejemplos")
