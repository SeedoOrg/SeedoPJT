# 필요한 라이브러리 import
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
import requests
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from PIL import ImageFont
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

# base 경로지정
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


# 한글 폰트 가져오기
font_file = os.path.join(BASE_DIR, "walking_mode/static/walking_mode/fonts/NanumGothic.ttf")
FONT = ImageFont.truetype(font_file)


# @token_required
def index(request):
    return render(request, "walking_mode/test2.html")


# 한글 표시 구현에 따른 기존 visioneye 메서드(cv2 ver.) 비호환에 따른 보완 메서드(PIL ver.) 추가
def visioneye_pil(self, box, center_point, color=(235, 219, 11), pin_color=(255, 0, 255)):
    center_bbox = int((box[0] + box[2]) / 2), int(box[3])
    self.draw.ellipse((center_point[0] - self.tf, center_point[1] - self.tf, center_point[0] + self.tf, center_point[1] + self.tf), fill=pin_color)
    self.draw.ellipse((center_bbox[0] - self.tf, center_bbox[1] - self.tf, center_bbox[0] + self.tf, center_bbox[1] + self.tf), fill=color)
    self.draw.line([center_point, center_bbox], fill=color, width=self.tf)


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


# 장애물 수직 방향 위치 결정 함수; near인 경우(not far)에 대해서만 음성안내 기능 작동
def get_y_loc(y_center, frame_height, threshold=4):
    if y_center < frame_height / threshold:  # threshold가 작을수록 시야가 좁아짐
        direction = "far"
    elif y_center < frame_height / threshold * 2:
        direction = "middle"
    elif y_center < frame_height / threshold * 3:
        direction = "reallynear"
    else:
        direction = "supernear"
    return direction


# 최적화된 캡션 생성 함수
def make_caption(history):
    history = history.sort_values(by=["dist", "dir"])
    result = []

    # 같은 cls, 같은 dir, dist <= 5인 경우 최솟값을 사용하여 그룹화
    filtered_history = history[history["dist"] <= 5]
    grouped = filtered_history.groupby(["cls", "dir"]).agg({"dist": "min", "cls": "size"}).rename(columns={"cls": "count"}).reset_index()

    # 기존 history에서 5m 이하인 것을 제거하고 나머지를 추가
    remaining_history = history[history["dist"] > 5]
    history = pd.concat([grouped, remaining_history], ignore_index=True).sort_values(by=["dist", "dir"])

    for dist, dist_group in history.groupby("dist"):
        dist_str = [f", {dist}미터", ", 멀리"][dist == 20]
        dist_result = []
        for dir, dir_group in dist_group.groupby("dir"):
            dir_str = f", {[dir, dir-12][dir > 12]}시"
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


# 모델 동작 요청을 받았을 때 동작하는 View
class ImageUploadView(View):
    template_name = "index.html"
    current_cls = 99  # 노면변화 감지용 변수
    frame_cnt = 0
    model_od = YOLO(yolo_od_pt)  #
    model_seg = YOLO(yolo_seg_pt)
    Annotator.visioneye_pil = visioneye_pil  # 라벨생성 Annotator

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        od_classes = []
        seg_classes = []
        history = []  # 한 프레임에 대해 묶어서 안내하기 위한 리스트
        pixel_per_meter = 120  # 거리 측정 민감도 파라미터

        if request.content_type == "application/json":
            # base64 이미지 디코딩
            data = json.loads(request.body)
            image_data = data.get("image_data")
            longitude = data.get("longitude")
            latitude = data.get("latitude")
            format, imgstr = image_data.split(";base64,")
            ext = format.split("/")[-1]
            image_data = ContentFile(base64.b64decode(imgstr), name="temp." + ext)
            nparr = np.frombuffer(image_data.read(), np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            # 디텍션 모델 실행
            od_classes, seg_classes, tts_audio_base64, annotated_image, complaints = self.process_image(
                img, self.model_od, self.model_seg, history, pixel_per_meter, longitude, latitude
            )
        else:
            return JsonResponse({"error": "Invalid content type"}, status=400)

        # 탐지결과 이미지 인코딩
        if annotated_image is not None:
            _, buffer = cv2.imencode(".webp", annotated_image)
            img_base64 = base64.b64encode(buffer).decode("utf-8")
        else:
            _, buffer = cv2.imencode(".webp", img)
            img_base64 = base64.b64encode(buffer).decode("utf-8")

        # 응답 요소 구성 (class정보, 모델, 음성, 이미지, 민원정보)
        response_data = {
            "od_classes": od_classes,
            "seg_classes": seg_classes,
            "tts_audio_base64": tts_audio_base64,
            "annotated_image": img_base64,
            "complaints": complaints,
        }

        return JsonResponse(response_data)

    @classmethod
    def process_image(self, img, model_od, model_seg, history, pixel_per_meter, longitude, latitude):
        current_update = False  # 노면 변화 탐지용 flag
        detected_obstacle = False  # 객체가 탐지되었는지 확인하는 flag
        complaints = None

        od_classes = []
        seg_classes = []
        tts_audio = []
        tts_audio_base64 = []

        w, h = img.shape[1], img.shape[0]
        start_point = (w // 2, h + pixel_per_meter * 2)
        _obstacles = [0, 1, 2, 3, 4, 5, 11, 12]

        frame_per_audio = 5  # 음성 안내 주기

        # 1프레임에 대해 2개의 디텍션 모델 예측 수행
        for i, model in enumerate([model_od, model_seg]):

            names = model.model.names
            names_kr = [OD_CLS_KR, SEG_CLS_KR][i]
            results = model.track(img, persist=True)  # 객체 추적기능 도입
            boxes = results[0].boxes.xyxy.cpu()
            clss = results[0].boxes.cls.int().cpu().tolist()

            # 만약 객체가 탐지 됐다면
            if results[0].boxes.id is not None:
                track_ids = results[0].boxes.id.int().cpu().tolist()
                for box, track_id, cls in zip(boxes, track_ids, clss):
                    if i == 0:  # Object Detection
                        od_classes.append(names[cls])
                    elif i == 1:  # Segmentation
                        seg_classes.append(names[cls])

                    # 파손 점자블록 탐지 시 민원신고 기능
                    if cls == 2 and i == 1:
                        base_url = "https://apis.openapi.sk.com/tmap/geo/reversegeocoding?version=1&format=json&callback=result"
                        params = {"lat": latitude, "lon": longitude, "coordType": "WGS84GEO", "addressType": "A10"}
                        headers = {"appKey": env("TMAP_API_KEY")}
                        response = requests.get(base_url, params=params, headers=headers)

                        if response.status_code == 200:
                            data = response.json()
                            address = data["addressInfo"]["fullAddress"].split(",")[2]
                        else:
                            print("Failed to connect API")
                            address = None

                        _, buffer = cv2.imencode(".webp", img)
                        complain_img = base64.b64encode(buffer).decode("utf-8")

                        # 민원 정보 추가
                        complaints = {"address": address, "img": complain_img}
                        continue

                    # 장애물 위치 정보 구하기
                    x1, y1 = int((box[0] + box[2]) // 2), int(box[3])  # label 표시용 위치
                    x_loc = get_x_loc(x1, w)  # 장애물 x,y위치 결정
                    y_loc = get_y_loc(y1, h, threshold=4)

                    # 현재 걷고 있는 노면은 무엇인가?
                    # 노면이고, 12시방향이고, 발 밑에 있다면
                    if (
                        (cls in [0, 1, 2, 3, 4, 5, 9, 11, 12])
                        and (x_loc == 12)
                        and (i == 1)
                        and (y_loc == "supernear")
                        and (ImageUploadView.frame_cnt % frame_per_audio == 0)  # 잦은 check 방지
                    ):
                        if self.current_cls != cls:  # 노면 정보가 바뀐 거라면 현재 노면 정보 업데이트
                            current_update = True
                            self.current_cls = cls

                    # segmentation인데, 장애물이 아니라면 pass
                    if (cls in _obstacles) and i == 1:
                        continue

                    # 여기까지 분기되지 않은 장애물들은 안내가 필요함.
                    annotator = Annotator(
                        img, line_width=3, example=str("가나다"), font=font_file
                    )  # 한글(유니코드) 사용; 내부적으로 cv2가 아닌 PIL로 처리
                    annotator.tf = max(annotator.lw - 1, 1)
                    detected_obstacle = True

                    # 유클리드 거리측정
                    distance = math.sqrt((x1 - start_point[0]) ** 2 + (y1 - start_point[1]) ** 2) / pixel_per_meter

                    if y_loc != "far":  # 수직 방향이 near인 경우에만 객체 알림
                        annotator.box_label(
                            box, label=f"{names_kr[cls]}{track_id}_{int(distance)}m_{[x_loc,x_loc-12][x_loc>12]}시", color=colors(cls)
                        )
                        annotator.visioneye_pil(box, start_point)

                        # 음성안내를 위한 객체 정보 추가
                        history.append({"dist": distance, "dir": x_loc, "cls": names_kr[cls]})

        # 현재 걷고 있는 노면이 바뀔 때 알림
        if current_update:
            msg = f"{names_kr[self.current_cls]}위를 걷고 있습니다!"
            tts_audio.append(naver_tts(msg))

        # 설정한 안내주기가 도달했을 때, history기반 음성안내
        if history and (ImageUploadView.frame_cnt % frame_per_audio == 0):
            history = pd.DataFrame(history)
            tmp = history["dist"]
            # 거리 양자화
            history["dist"] = np.where(tmp > 20, 20, np.where(tmp > 15, 15, np.where(tmp > 10, 10, np.where(tmp > 5, 5, tmp.astype(int)))))
            msg = make_caption(history)
            tts_audio.append(naver_tts(msg))

        # 생성된 오디오가 있다면, base64인코딩해서 리스트에 추가
        if tts_audio != []:
            for i in tts_audio:
                tts_audio_base64.append(base64.b64encode(i).decode("utf-8"))

        ImageUploadView.frame_cnt += 1
        annotated_image = annotator.result() if detected_obstacle else None
        current_update = False
        return od_classes, seg_classes, tts_audio_base64, annotated_image, complaints
