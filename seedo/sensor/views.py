# Create your views here.
# sensor/views.py
import json

import numpy as np
import pandas as pd
from common.decorators import token_required
from django.http import JsonResponse
from django.shortcuts import render
from joblib import load
from keras.models import load_model
from scipy.fftpack import fft
from scipy.stats import median_abs_deviation


@token_required
def get_sensor(request):

    return render(request, "sensor/index.html")


model = load_model("sensor/ml_models/sensor/ml_model/fall_recognition_gyro.h5")


@token_required
def fall_recognition(request):
    if request.method == "POST":
        data = json.loads(request.body)
        df = process_sensor_data(data)
        scaler = load("sensor/ml_models/sensor/scaler/scaler_gyro.joblib")
        X_test = df
        X_test_normalized = scaler.transform(X_test)
        time_steps = 15

        num_test_samples = (X_test_normalized.shape[0] // time_steps) * time_steps

        X_test_final = X_test_normalized[:num_test_samples]

        X_test_final = X_test_final.reshape((num_test_samples // time_steps, time_steps, X_test_final.shape[1]))

        y_pred = model.predict(X_test_final)
        prediction = np.argmax(y_pred, axis=1)
        return JsonResponse({"prediction": prediction.tolist()})
    return JsonResponse({"error": "Invalid request method"}, status=400)


def process_sensor_data(data):
    columns = [
        "Time(s)",
        "acc_x(g)",
        "acc_y(g)",
        "acc_z(g)",
        "gyr_x(deg/s)",
        "gyr_y(deg/s)",
        "gyr_z(deg/s)",
        "SVM_acc(g)",
        "SVM_gyro(g)",
        "SVM_acc(g)_mean",
        "SVM_acc(g)_std",
        "SVM_acc(g)_median",
        "SVM_acc(g)_mad",
        "SVM_gyro(g)_mean",
        "SVM_gyro(g)_std",
        "SVM_gyro(g)_median",
        "SVM_gyro(g)_mad",
        "SVM_acc(g)_fft_mean",
        "SVM_acc(g)_fft_std",
        "SVM_gyro(g)_fft_mean",
        "SVM_gyro(g)_fft_std",
    ]

    rows = []

    previousAlpha, previousBeta, previousGamma = None, None, None
    previousTime = None
    sensor_datas = data["sensor_data"]

    for sensor_data in sensor_datas:
        time = sensor_data["timestamp"] / 1000
        acc = sensor_data["acc"]
        gyro = sensor_data["gyro"]

        acc_x = acc["x"]
        acc_y = acc["y"]
        acc_z = acc["z"]
        currentAlpha = gyro["alpha"]
        currentBeta = gyro["beta"]
        currentGamma = gyro["gamma"]

        if previousAlpha is None:
            previousAlpha, previousBeta, previousGamma = (currentAlpha, currentBeta, currentGamma)
            previousTime = time
            continue

        deltaTime = time - previousTime

        gyr_x = updateAlpha(previousAlpha, currentAlpha) / deltaTime
        gyr_y = updateBeta(previousBeta, currentBeta) / deltaTime
        gyr_z = updateGamma(previousGamma, currentGamma) / deltaTime

        SVM_acc = np.sqrt(acc_x**2 + acc_y**2 + acc_z**2)
        SVM_gyro = np.sqrt(gyr_x**2 + gyr_y**2 + gyr_z**2)

        rows.append(
            {
                "Time(s)": time,
                "acc_x(g)": acc_x,
                "acc_y(g)": acc_y,
                "acc_z(g)": acc_z,
                "gyr_x(deg/s)": gyr_x,
                "gyr_y(deg/s)": gyr_y,
                "gyr_z(deg/s)": gyr_z,
                "SVM_acc(g)": SVM_acc,
                "SVM_gyro(g)": SVM_gyro,
            }
        )

    df = pd.DataFrame(rows, columns=columns)

    # 새로운 컬럼 피처 엔지니어링
    # LSTM 윈도우 사이즈: 1/30초 * 15(window_size) > 0.5초 구간간격으로 넘어짐 판단
    window_size = 15
    df["SVM_acc(g)_mean"] = df["SVM_acc(g)"].rolling(window=window_size).mean()
    df["SVM_acc(g)_std"] = df["SVM_acc(g)"].rolling(window=window_size).std()
    df["SVM_acc(g)_median"] = df["SVM_acc(g)"].rolling(window=window_size).median()
    df["SVM_acc(g)_mad"] = df["SVM_acc(g)"].rolling(window=window_size).apply(median_abs_deviation)

    df["SVM_gyro(g)_mean"] = df["SVM_gyro(g)"].rolling(window=window_size).mean()
    df["SVM_gyro(g)_std"] = df["SVM_gyro(g)"].rolling(window=window_size).std()
    df["SVM_gyro(g)_median"] = df["SVM_gyro(g)"].rolling(window=window_size).median()
    df["SVM_gyro(g)_mad"] = df["SVM_gyro(g)"].rolling(window=window_size).apply(median_abs_deviation)

    def calculate_fft_features(signal):
        signal = np.array(signal)
        fft_values = fft(signal)
        fft_magnitude = np.abs(fft_values)
        return np.mean(fft_magnitude), np.std(fft_magnitude)

    df["SVM_acc(g)_fft_mean"] = (
        df["SVM_acc(g)"].rolling(window=window_size).apply(lambda x: calculate_fft_features(x)[0] if len(x) == window_size else np.nan)
    )
    df["SVM_acc(g)_fft_std"] = (
        df["SVM_acc(g)"].rolling(window=window_size).apply(lambda x: calculate_fft_features(x)[1] if len(x) == window_size else np.nan)
    )

    df["SVM_gyro(g)_fft_mean"] = (
        df["SVM_gyro(g)"].rolling(window=window_size).apply(lambda x: calculate_fft_features(x)[0] if len(x) == window_size else np.nan)
    )
    df["SVM_gyro(g)_fft_std"] = (
        df["SVM_gyro(g)"].rolling(window=window_size).apply(lambda x: calculate_fft_features(x)[1] if len(x) == window_size else np.nan)
    )

    drop_cols = ["Time(s)"]

    df.dropna(inplace=True)
    df.drop(columns=drop_cols, inplace=True)

    return df


def updateAlpha(previousAlpha, currentAlpha):
    delta = currentAlpha - previousAlpha
    if delta > 180:
        delta -= 360
    elif delta < -180:
        delta += 360

    return delta


def updateBeta(previousBeta, currentBeta):
    delta = currentBeta - previousBeta
    if delta > 180:
        delta -= 360
    elif delta < -180:
        delta += 360

    return delta


def updateGamma(previousGamma, currentGamma):
    delta = currentGamma - previousGamma
    if delta > 90:
        delta -= 180
    elif delta < -90:
        delta += 180

    return delta
