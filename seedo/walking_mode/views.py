import base64
import json
import math
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

import cv2
import environ
import numpy as np
from django.conf import settings
from django.core.files.base import ContentFile
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from ultralytics import YOLO
from ultralytics.utils.plotting import Annotator, colors

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


# 프레임수 줄여주는 코드
# def reduce_fps(input_video_path, fps_video_path, target_fps=2):
#     # 비디오 파일 열기
#     cap = cv2.VideoCapture(input_video_path)
#     if not cap.isOpened():
#         print("Error opening video file")
#         return

#     # 원본 비디오의 FPS 및 프레임 크기 가져오기
#     original_fps = cap.get(cv2.CAP_PROP_FPS)
#     frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
#     frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

#     # 출력 비디오 설정
#     fourcc = cv2.VideoWriter_fourcc(*"mp4v")
#     # 오리지널 패스에 같은 크기로 사진 저장
#     out = cv2.VideoWriter(fps_video_path, fourcc, target_fps, (frame_width, frame_height))

#     # FPS 감소 비율 계산
#     fps_ratio = original_fps / target_fps

#     frame_count = 0
#     while cap.isOpened():
#         ret, frame = cap.read()
#         if not ret:
#             break

#         # 지정된 비율에 따라 프레임 쓰기
#         if frame_count % int(fps_ratio) == 0:
#             out.write(frame)

#         frame_count += 1

#     # 비디오 파일 닫기
#     cap.release()
#     out.release()
#     print(f"Finished reducing FPS from {original_fps} to {target_fps}. Output saved to {fps_video_path}")


# 위치 결정 함수
def determine_position(x_center):
    # yolo 모델 이미지 사이즈
    image_width = 640
    if x_center < image_width / 5:
        direction = "10시 방향"
    elif x_center < 2 * image_width / 5:
        direction = "11시 방향"
    elif x_center < 3 * image_width / 5:
        direction = "12시 방향"
    elif x_center < 4 * image_width / 5:
        direction = "1시 방향"
    else:
        direction = "2시 방향"
    return direction


class ImageUploadView(View):
    template_name = "test2.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        try:  # 모델 불러오기
            model_od = YOLO(yolo_od_pt)
            model_seg = YOLO(yolo_seg_pt)
            model_od.names
            model_seg.names
        except Exception as e:
            print(f"Error loading models: {str(e)}")
            return JsonResponse({"error": f"Error loading models: {str(e)}"}, status=500)

        od_classes = []
        seg_classes = []
        tts_audio_url = None  # 초기화
        history = {}
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
            od_classes, seg_classes, tts_audio_url, annotated_image = self.process_image(img, model_od, model_seg, history, pixel_per_meter)
        else:
            return JsonResponse({"error": "Invalid content type"}, status=400)

        if annotated_image is not None:
            _, buffer = cv2.imencode(".jpg", annotated_image)
            img_base64 = base64.b64encode(buffer).decode("utf-8")
        else:
            img_base64 = None

        return JsonResponse({"od_classes": od_classes, "seg_classes": seg_classes, "tts_audio_url": tts_audio_url, "annotated_image": img_base64})

    def process_image(self, img, model_od, model_seg, history, pixel_per_meter):
        w, h = img.shape[1], img.shape[0]
        start_point = (w // 2, h + pixel_per_meter * 2)
        _obstacles = [0, 1, 2, 3, 4, 5, 11, 12]

        current_track_ids = []
        tts_text = None  # 초기화
        tts_audio_url = None  # 초기화
        od_classes = []
        seg_classes = []
        annotator = Annotator(img, line_width=2)
        txt_color, txt_background = ((0, 0, 0), (255, 255, 255))

        detected_obstacle = False  # 객체가 탐지되었는지 확인하는 플래그

        # 모델 2개 순회
        for i, model in enumerate([model_od, model_seg]):
            names = model.model.names
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
                    distance = math.sqrt((x1 - start_point[0]) ** 2 + (y1 - start_point[1]) ** 2) / pixel_per_meter

                    annotator.box_label(box, label=f"{names[int(cls)]}_{track_id}", color=colors(int(cls)))
                    annotator.visioneye(box, start_point)
                    text_size, _ = cv2.getTextSize(f"Distance: {distance:.2f} m", cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(img, (x1, y1 - text_size[1] - 10), (x1 + text_size[0] + 10, y1), txt_background, -1)
                    cv2.putText(img, f"Distance: {distance:.2f} m", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, txt_color, 1)

                    current_track_ids.append(track_id)

                    if track_id not in history:
                        history[track_id] = {"cls": cls, "count": 0, "model": i}
                    if distance <= 5:  # 5m 안쪽에 들어왔으면 +1 시작.
                        history[track_id]["count"] += 1

                    if history[track_id]["count"] >= 1:  # 테스트를 위해 최초 탐지시 출력하도록 설정.
                        direction = determine_position(x1)
                        cls_count = sum(1 for h in history.values() if (h["cls"] == cls and h["model"] == i))
                        if cls_count >= 3:  # 같은 객체 다수탐지 case
                            if 3 <= distance <= 7:
                                tts_text = f"7m, {direction}, {names[int(cls)]},{cls_count}개"
                            elif distance < 3:
                                tts_text = f"3m, {direction}, {names[int(cls)]},{cls_count}개"

                            for k, v in history.items():
                                if v["cls"] == cls and v["model"] == i:
                                    v["count"] = -20
                        else:  # 단일 객체 탐지 case
                            if 3 <= distance <= 7:
                                tts_text = f"7m,{direction}, {names[int(cls)]}"
                            elif distance < 7:
                                tts_text = f"3m,{direction}, {names[int(cls)]}"
                        history[track_id]["count"] = -10  # 한 번 등장시 한동안 등장하지 않도록
                        # tts 출력
                        try:
                            if tts_text:
                                tts_audio = naver_tts(tts_text)
                                if tts_audio:
                                    tts_audio_dir = os.path.join(settings.MEDIA_ROOT, "tts_audio")
                                    if not os.path.exists(tts_audio_dir):
                                        os.makedirs(tts_audio_dir)
                                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                                    tts_audio_path = os.path.join(tts_audio_dir, f"tts_audio_{timestamp}.mp3")
                                    with open(tts_audio_path, "wb") as f:
                                        f.write(tts_audio)
                                    tts_audio_url = settings.MEDIA_URL + f"tts_audio/tts_audio_{timestamp}.mp3"
                        except Exception as e:
                            print(f"TTS Error: {str(e)}")
        for track_id in list(history.keys()):
            if track_id not in current_track_ids:
                del history[track_id]
        print(history)
        annotated_image = annotator.result() if detected_obstacle else None
        return od_classes, seg_classes, tts_audio_url, annotated_image


# 파일 업로드방식.
# if request.FILES.get("file"):
#             file = request.FILES["file"]
#             file_path = os.path.join(settings.MEDIA_ROOT, "video.mp4")
#             with open(file_path, "wb+") as destination:
#                 for chunk in file.chunks():
#                     destination.write(chunk)

#             # 비디오 파일이라면!
#             if file.content_type.startswith("video"):
#                 # fps 줄이기
#                 target_fps = 2
#                 fps_video_path = f"{file_path[:-4]}_fps{target_fps}.mp4"
#                 reduce_fps(file_path, fps_video_path, target_fps)

#                 tts_text = None
#                 history = {}
#                 cap = cv2.VideoCapture(fps_video_path)

#                 od_classes = []
#                 seg_classes = []

#                 pixel_per_meter = 300

#                 w, h, fps = (int(cap.get(x)) for x in (cv2.CAP_PROP_FRAME_WIDTH, cv2.CAP_PROP_FRAME_HEIGHT, cv2.CAP_PROP_FPS))
#                 # out = cv2.VideoWriter(output_video_path, cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h))
#                 txt_color, txt_background = ((0, 0, 0), (255, 255, 255))  # 거리 표시를 위한 텍스트 및 배경 색

#                 _obstacles = [0, 1, 2, 3, 4, 5, 11, 12]  # 장애물이 아닌 탐지 클래스

#                 start_point = (w // 2, h + pixel_per_meter * 2)  # 사용자의 발끝 시작점

#                 # complaints = [] # 민원

#                 while True:
#                     ret, frame = cap.read()  # ret: 프레임 존재 boolean , frame: ret = true일때 나오는값
#                     if not ret:
#                         print("Video frame is empty or video processing has been successfully completed.")
#                         break
#                     annotator = Annotator(frame, line_width=2)

#                     current_track_ids = []

#                     for i, model in enumerate([model_od, model_seg]):  # 현재 프레임에 대해 OD, Seg 적용
#                         names = model.model.names  # 클래스 정보 딕셔너리(key: 번호, value: 클래스 이름)
#                         # results = model.predict(frame)
#                         results = model.track(frame, persist=True)  # conf=0.3, iou=0.5 # 객체 추적 예측
#                         boxes = results[0].boxes.xyxy.cpu()  # 객체 B-box 좌표
#                         clss = results[0].boxes.cls.cpu().tolist()  # 객체 클래스 번호

#                         if results[0].boxes.id is not None:  # 객체 예측 결과가 존재하는 경우
#                             track_ids = results[0].boxes.id.int().cpu().tolist()  # 객체 추적을 위한 고유 번호

#                             for box, track_id, cls in zip(boxes, track_ids, clss):  # 장애물 정보 순회
#                                 if (int(cls) in _obstacles) and i == 1:  # 장애물이 아닌 경
#                                     continue

#                                 # 장애물인 경우 처리
#                                 x1, y1 = int((box[0] + box[2]) // 2), int(box[3])  # B-box 밑변 중점
#                                 # x1, y1 = int((box[0] + box[2]) // 2), int((box[1] + box[3]) // 2)  # B-box 전체 중점
#                                 distance = (
#                                     math.sqrt((x1 - start_point[0]) ** 2 + (y1 - start_point[1]) ** 2)
#                                 ) / pixel_per_meter  # 발끝과의 거리 계산; 장애물과의 예상 거리

#                                 annotator.box_label(box, label=f"{names[int(cls)]}_{track_id}", color=colors(int(cls)))
#                                 annotator.visioneye(box, start_point)
#                                 text_size, _ = cv2.getTextSize(f"Distance: {distance:.2f} m", cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
#                                 cv2.rectangle(frame, (x1, y1 - text_size[1] - 10), (x1 + text_size[0] + 10, y1), txt_background, -1)
#                                 cv2.putText(frame, f"Distance: {distance:.2f} m", (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, txt_color, 1)

#                                 current_track_ids.append(track_id)  # 한 개 이미지 내 2개 모델결과에 대한 list

#                                 if track_id not in history:
#                                     history[track_id] = {
#                                         "cls": cls,
#                                         "count": 0,
#                                         "model": i,
#                                     }  # history에 없다면 해당 track_id선언, 초기화,   #history에 있었다면 +1
#                                 # print(distance)
#                                 if distance <= 7:
#                                     history[track_id]["count"] += 1

#                                 if history[track_id]["count"] >= 4:  # 4프레임 연속 등장한 track_id라면
#                                     direction = determine_position(x1)  # 10시방향, 11시방향...

#                                     cls_count = sum(
#                                         1 for h in history.values() if (h["cls"] == cls and h["model"] == i)
#                                     )  # 같은 클래스가 history에 몇 개 있는지 세기.
#                                     if cls_count >= 3:
#                                         if 3 <= distance <= 7:
#                                             tts_text = f"7m, {direction}, {names[int(cls)]},{cls_count}개"  # 네이버 api연결 함수.

#                                         elif distance < 3:
#                                             tts_text = f"3m, {direction}, {names[int(cls)]},{cls_count}개"

#                                         for k, v in history.items():  # 중복 탐지 된 track_id들 묶어서, 20프레임 동안 다시 안내 하지 않도록
#                                             if v["cls"] == cls and v["model"] == i:
#                                                 v["count"] = -20
#                                     else:
#                                         if 3 <= distance <= 7:
#                                             tts_text = f"5m,{direction}, {names[int(cls)]}"

#                                         elif distance < 7:
#                                             tts_text = f"3m,{direction}, {names[int(cls)]}"
#                                     history[track_id]["count"] = -10  # 한 번 tts로 나오면 5초간은 중복해서 나오지 않도록 구성. (10프레임 =5초)
#                                     try:
#                                         print(tts_text)
#                                         tts_audio = naver_tts(tts_text)
#                                         if tts_audio:
#                                             tts_audio_dir = os.path.join(settings.MEDIA_ROOT, "tts_audio")
#                                             if not os.path.exists(tts_audio_dir):
#                                                 os.makedirs(tts_audio_dir)
#                                             timestamp = time.strftime("%Y%m%d-%H%M%S")  # 현재 시간을 기반으로 고유한 이름 생성
#                                             tts_audio_path = os.path.join(tts_audio_dir, f"tts_audio_{timestamp}.mp3")
#                                             with open(tts_audio_path, "wb") as f:
#                                                 f.write(tts_audio)
#                                             tts_audio_url = f"media/tts_audio/tts_audio_{timestamp}.mp3"
#                                             print("TTS Audio Path:", tts_audio_path)  # 로그 추가
#                                             print("TTS Audio URL:", tts_audio_url)  # 로그 추가
#                                     except Exception as e:
#                                         print(f"TTS Error: {str(e)}")
#                     # 현재 사진에 없는 장애물을 history에서 지우는 코드
#                     for track_id in list(history.keys()):
#                         if track_id not in current_track_ids:
#                             del history[track_id]
#                     print(f"history: {history}")  # history출력해보기.

# out.write(frame) # 프레임 저장
# cv2_imshow(frame)

# if frame_count % frame_interval == 0:

#     # 객체 탐지
#     results_od = model_od.track(frame, conf=0.3, iou=0.5, persist=True)
#     results_seg = model_seg.track(frame, conf=0.3, iou=0.5, persist=True)

#     boxes = results_od[0].boxes.xyxy.cpu() # 객체 B-box 좌표
#     clss = results_od[0].boxes.cls.cpu().tolist() # 객체 클래스 번호

#     # 객체 클래스 추출
#     if results_od and results_od[0].boxes:
#         od_classes = [names_od[int(cls)] for cls in results_od[0].boxes.cls]
#     else:
#         od_classes = []

#     if results_seg and results_seg[0].boxes:
#         seg_classes = [names_seg[int(cls)] for cls in results_seg[0].boxes.cls]
#     else:
#         seg_classes = []
# frame_count += 1

# cap.release()
