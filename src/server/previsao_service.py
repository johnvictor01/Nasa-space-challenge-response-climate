import os
import numpy as np
import sys

# Adiciona a pasta src ao sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Agora podemos importar diretamente de utils
from utils.preprocessing import criar_features_ciclicas
from utils.helpers import corrigir_falsos_negativos
from utils.io_utils import carregar_modelos

campos = ['temp_media_c','temp_max_c','temp_min_c','umidade_pct','precipitacao_mm','vento_kmh']

def prever_cidade_data(cidade, data, model_dir=None):
    """
    Gera previsão para uma cidade/data.
    model_dir: se None, usa src/data/modelos (multiplataforma).
    """
    if model_dir is None:
        model_dir = os.path.join("src", "data", "modelos")

    mes = data.month
    dia = data.day

    # cria features e garante formato 2D adequado para scaler / predict
    X_input = criar_features_ciclicas(dia, mes)
    X_input = np.asarray(X_input)
    if X_input.ndim == 1:
        X_input = X_input.reshape(1, -1)  # uma linha, n features

    cidade_path = os.path.join(model_dir, cidade)
    # Debug mínimo para confirmar presença dos modelos no ambiente
    print(f"[DEBUG] procurando modelos em: {cidade_path} (exists={os.path.exists(cidade_path)})")
    if os.path.exists(cidade_path):
        try:
            print(f"[DEBUG] arquivos em {cidade_path}: {os.listdir(cidade_path)}")
        except Exception as e:
            print(f"[DEBUG] erro listando {cidade_path}: {e}")

    previsao = {'cidade': cidade, 'data': data.strftime("%Y-%m-%d")}

    for campo in campos:
        modelos, scaler = carregar_modelos(cidade_path, campo)

        if not modelos:
            previsao[campo] = None
            continue

        previsoes = []
        for modelo in modelos:
            # aplica scaler se existir
            X_scaled = scaler.transform(X_input) if scaler else X_input
            pred = modelo.predict(X_scaled)
            # garante extrair um valor escalar (primeira linha/predição)
            valor = float(pred[0]) if hasattr(pred, "__len__") else float(pred)
            previsoes.append(corrigir_falsos_negativos(valor, campo))

        # converte None -> np.nan para poder usar np.nanmean com segurança
        vals = [float(v) if v is not None else np.nan for v in previsoes]
        media = np.nanmean(vals)
        previsao[campo] = float(round(media, 2)) if not np.isnan(media) else None

    # default para precipitação
    if previsao.get("precipitacao_mm") is None:
        previsao["precipitacao_mm"] = 0.0

    # Heurísticas: use (valor or 0) para evitar None >= int
    previsao["VaiChover"] = bool((previsao.get("precipitacao_mm") or 0) >= 1)
    previsao["DiaQuente"] = bool((previsao.get("temp_max_c") or 0) >= 30)
    previsao["DiaFrio"] = bool((previsao.get("temp_min_c") or 0) <= 18)
    previsao["DiaVentoso"] = bool((previsao.get("vento_kmh") or 0) >= 20)
    previsao["DiaConfortavel"] = bool(
        previsao.get("temp_media_c") is not None
        and 20 <= previsao["temp_media_c"] <= 28
        and (previsao.get("umidade_pct") or 0) <= 70
        and not previsao.get("VaiChover", False)
    )

    return previsao
