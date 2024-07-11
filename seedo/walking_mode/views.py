import base64
import json
import math
import os
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import environ
import numpy as np
import pandas as pd
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from ultralytics import YOLO
from ultralytics.utils.plotting import Annotator, colors

# 클래스 한글 이름
OD_CLS_KR = ["휠체어", "유모차", "정류장", "킥보드", "기둥", "이동식 간판", "오토바이", "소화전", "강아지", "볼라드", "자전거", "벤치", "바리케이드"]
SEG_CLS_KR = [
    "인도",
    "점자블록",
    "파손점자블록",
    "차도",
    "공용도로",
    "자전거도로",
    "하수구그레이팅",
    "맨홀",
    "보수구역",
    "계단",
    "가로수",
    "횡단보도",
    "횡단보도",
]

BASE_DIR = Path(__file__).resolve().parent.parent

# pt 파일가져오기
yolo_od_pt = os.path.join(BASE_DIR, "walking_mode/pt_files/yolov8n_epoch20.pt")
yolo_seg_pt = os.path.join(BASE_DIR, "walking_mode/pt_files/yolov8s_epoch50.pt")

# API 가져오기
env = environ.Env(
    # set casting, default value
    DEBUG=(bool, False)
)
env_path = BASE_DIR.parent / ".env"
environ.Env.read_env(env_file=env_path)

CLIENT_ID = env("NAVER_TTS_CLIENT_ID")
SECRETE_KEY = env("NAVER_TTS_CLIENT_SECRETE_KEY")


# @token_required
def index(request):
    return render(request, "walking_mode/test2.html")


# tts api
def naver_tts(text):
    try:
        encText = urllib.parse.quote(text)
        data = f"speaker=nara&volume=0&speed=0&pitch=0&format=mp3&text={encText}"
        url = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"

        request_api = urllib.request.Request(url)
        request_api.add_header("X-NCP-APIGW-API-KEY-ID", CLIENT_ID)
        request_api.add_header("X-NCP-APIGW-API-KEY", SECRETE_KEY)

        response = urllib.request.urlopen(request_api, data=data.encode("utf-8"))
        rescode = response.getcode()

        if rescode == 200:
            response_body = response.read()
            return response_body
        else:
            raise Exception(f"Error Code: {rescode}")
    except urllib.error.HTTPError as e:
        raise Exception(f"HTTPError: {e.code} {e.reason}")
    except urllib.error.URLError as e:
        raise Exception(f"URLError: {e.reason}")
    except Exception as e:
        raise Exception(str(e))


# 장애물 수평 방향 위치 결정 함수
def get_x_loc(x_center, frame_width):
    if x_center < frame_width / 7:
        direction = 10
    elif x_center < 3 * frame_width / 7:
        direction = 11
    elif x_center < 4 * frame_width / 7:
        direction = 12
    elif x_center < 6 * frame_width / 7:
        direction = 13
    else:
        direction = 14
    return direction


# 장애물 수직 방향 위치 결정 함수; near인 경우에 대해서만 기능 작동
def get_y_loc(y_center, frame_height, threshold=4):
    if y_center < frame_height / threshold:  # threshold가 작을수록 시야가 좁아짐
        direction = "far"
    else:
        direction = "near"
    return direction


# 최적화된 캡션 생성 함수
def make_caption(history):
    history = history.sort_values(by=["dist", "dir"])
    result = []
    for dist, dist_group in history.groupby("dist"):
        dist_str = [f", {dist}미터", ", 멀리"][dist == 25]
        dist_result = []
        for dir, dir_group in dist_group.groupby("dir"):
            dir_str = f", {[dir,dir-12][dir>12]}시"
            dir_result = []
            for cls, cls_group in dir_group.groupby("cls"):
                cls_str = cls
                cls_cnt = len(cls_group)
                if cls_cnt > 1:
                    cls_str += f" {cls_cnt}{['개','마리'][cls=='강아지']}"
                dir_result.append(cls_str)
            dist_result.append(f"{dir_str} " + " ".join(dir_result))
        result.append(f"{dist_str} " + " ".join(dist_result))
    return " ".join(result)


class ImageUploadView(View):
    template_name = "test2.html"
    frame_cnt = 0
    model_od = YOLO(yolo_od_pt)
    model_seg = YOLO(yolo_seg_pt)

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        od_classes = []
        seg_classes = []
        tts_audio_base64 = None  # 초기화
        history = []
        pixel_per_meter = 120

        # 카메라에서 불러오는 방식
        if request.content_type == "application/json":
            data = json.loads(request.body)
            image_data = data.get("image_data")
            format, imgstr = image_data.split(";base64,")
            ext = format.split("/")[-1]
            image_data = ContentFile(base64.b64decode(imgstr), name="temp." + ext)
            nparr = np.frombuffer(image_data.read(), np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            od_classes, seg_classes, tts_audio_base64, annotated_image = self.process_image(
                img, self.model_od, self.model_seg, history, pixel_per_meter
            )
        else:
            return JsonResponse({"error": "Invalid content type"}, status=400)

        if annotated_image is not None:
            _, buffer = cv2.imencode(".jpg", annotated_image)
            img_base64 = base64.b64encode(buffer).decode("utf-8")
        else:
            img_base64 = None

        response_data = {"od_classes": od_classes, "seg_classes": seg_classes, "tts_audio_base64": tts_audio_base64, "annotated_image": img_base64}

        return JsonResponse(response_data)

    @classmethod
    def process_image(self, img, model_od, model_seg, history, pixel_per_meter):
        frame_per_audio = 5
        w, h = img.shape[1], img.shape[0]
        start_point = (w // 2, h + pixel_per_meter * 2)
        _obstacles = [0, 1, 2, 3, 4, 5, 11, 12]

        tts_audio_base64 = None  # 초기화
        od_classes = []
        seg_classes = []

        annotator = Annotator(img, line_width=2)
        txt_color, txt_background = ((0, 0, 0), (255, 255, 255))

        detected_obstacle = False  # 객체가 탐지되었는지 확인하는 플래그

        # 모델 2개 순회
        for i, model in enumerate([model_od, model_seg]):
            names = model.model.names
            [OD_CLS_KR, SEG_CLS_KR][i]
            results = model.track(img, persist=True)
            boxes = results[0].boxes.xyxy.cpu()
            clss = results[0].boxes.cls.cpu().tolist()

            # 만약 객체가 탐지 됐다면
            if results[0].boxes.id is not None:
                track_ids = results[0].boxes.id.int().cpu().tolist()
                for box, track_id, cls in zip(boxes, track_ids, clss):
                    if i == 0:  # Object Detection
                        od_classes.append(names[int(cls)])
                    elif i == 1:  # Segmentation
                        seg_classes.append(names[int(cls)])
                    if (int(cls) in _obstacles) and i == 1:
                        continue
                    detected_obstacle = True

                    x1, y1 = int((box[0] + box[2]) // 2), int(box[3])
                    x_loc = get_x_loc(x1, w)
                    y_loc = get_y_loc(y1, h, threshold=4)
                    distance = math.sqrt((x1 - start_point[0]) ** 2 + (y1 - start_point[1]) ** 2) / pixel_per_meter

                    if y_loc == "near":  # 수직 방향이 near인 경우에만 객체 알림
                        annotator.box_label(box, label=f"{names[int(cls)]}_{track_id}", color=colors(int(cls)))
                        annotator.visioneye(box, start_point)
                        text_size, _ = cv2.getTextSize(f"Distance: {int(distance)}m", cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                        cv2.rectangle(img, (x1, y1 - text_size[1] - 10), (x1 + text_size[0] + 10, y1), txt_background, -1)
                        cv2.putText(img, f"Distance: {int(distance)}m", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, txt_color, 1)

                        # 음성안내를 위한 객체 정보 추가
                        history.append({"dist": distance, "dir": x_loc, "cls": names[int(cls)]})

        if history and (ImageUploadView.frame_cnt % frame_per_audio == 0):
            history = pd.DataFrame(history)
            tmp = history["dist"]
            history["dist"] = np.where(
                tmp > 25,
                25,  # 멀리
                np.where(
                    tmp > 20, 20, np.where(tmp > 15, 15, np.where(tmp > 10, 10, np.where(tmp > 5, 5, tmp.astype(int))))  # 20m  # 15m  # 10m  # 5m
                ),
            )  # 가까우면 정수로 내림
            msg = make_caption(history)
            tts_audio = naver_tts(msg)
            if tts_audio:
                tts_audio_base64 = base64.b64encode(tts_audio).decode("utf-8")
        ImageUploadView.frame_cnt += 1
        annotated_image = annotator.result() if detected_obstacle else None
        return od_classes, seg_classes, tts_audio_base64, annotated_image
