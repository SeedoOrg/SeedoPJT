import base64
import urllib.parse
import urllib.request
from io import BytesIO
from pathlib import Path

import environ
import openai
from common.decorators import token_required
from django.http import JsonResponse
from django.shortcuts import render
from PIL import Image

# 환경변수 호출
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR.parent / ".env"
env = environ.Env(DEBUG=(bool, False))
env_path = BASE_DIR.parent / ".env"
environ.Env.read_env(env_file=env_path)

CLIENT_ID = env("NAVER_TTS_CLIENT_ID")
SECRETE_KEY = env("NAVER_TTS_CLIENT_SECRETE_KEY")


# openapi 정의
client = openai.OpenAI()


@token_required
def index(request):
    return render(request, "ocr/index.html")


def capture(request):
    if request.method == "POST":  # 요청이 POST인지 확인합니다.
        image_data = request.POST.get("image_data")  # 이미지 데이터를 폼 데이터에서 가져옵니다.
        if image_data:
            image_data = base64.b64decode(image_data.split(",")[1])  # base64로 인코딩된 이미지 데이터를 디코딩합니다.

            image = Image.open(BytesIO(image_data))

            # 이미지 형식 및 크기 검증
            if image.format.lower() not in ["jpeg", "png", "gif", "webp"]:
                return JsonResponse({"error": "Unsupported image format"}, status=400)

            if len(image_data) > 20 * 1024 * 1024:  # 20MB 제한
                return JsonResponse({"error": "Image size exceeds 20MB"}, status=400)

            # 이미지 데이터를 base64로 다시 인코딩
            buffered = BytesIO()
            image.save(buffered, format=image.format)
            image_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": """당신은 유능한 한국의 시각장애인 시각보조장치입니다. 다음 규칙을 지키지 않으면 시각장애인에게 치명적인 문제를 일으킵니다. 다음 규칙을 절대적으로 지키며 이미지의 글자를 읽어주세요.
                                                1. 정확하지 않은거나 사진에 없는 내용은 말하지 마세요.
                                                2. 명확하지 글에 대해서는 무조건 인식하기 어렵고 출력되는 내용이 정확하지 않을 수 있다고 말합니다.
                                                3. 글자가 선명하지 않다면 사진이 선명하지 않으니 다시 찍어달라고 안내합니다.
                                                4. 선명하지 않은 긴글은 페이지당 100글자 이내로 요약하여 말하세요.
                                                5. 당신의 지식을 이용해서 사진에 없는 내용을 판단하여 지어내는 행위를 절대 하지마세요.
                                                6. 의약품, 주의사항, 위험물, 의료정보, 안전정보 와 같은 내용에서는 5번을 절대적으로 지키세요.
                                                7. 정확하게 읽은 문장이 아니면 읽지 마세요.
                                                8. 당신의 주요 역할은 글자를 읽어주는 것입니다. 읽을 글자가 없다면 반드시 안내하세요.
                                                9. 글과 그림이 있다면 글은 읽고 그림에 대해서 설명하세요.
                                                10. 글자가 없을때는 글자가 없다고 말하고 주변환경을 아주 짧게 설명하세요.
                                                11. 글자가 있다면 글자가 없다고 말하고 주변환경을 설명하지 마세요.
                                                12. 돈이 보인다면 반드시 다음 양식으로만 대답해라 " X원 화폐 X개,X원 화폐 X개... 총 X원 입니다. 금액이 정화하지 않을 수 있으니 반드시 다시 확인하세요."
                                                13. 버스가 보인다면 보이는 정보에 대해 다음 양식으로만 대답해라 "X색의 X번 버스가 있습니다, 버스에는 X라는 글자가 적혀있습니다."
                                                    단 정보가 없다면 그정보는 제외하라""",
                    },
                    {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/webp;base64,{image_base64}"}}]},
                ],
                temperature=0.0,
                top_p=0.65,
                frequency_penalty=0.8,
            )
            answer = response.choices[0].message.content
            print(answer)

            # tts 출력
            try:
                if answer:
                    tts_audio = naver_tts(answer)
                    if tts_audio:
                        tts_audio_base64 = base64.b64encode(tts_audio).decode("utf-8")
            except Exception as e:
                print(f"TTS Error: {str(e)}")

            return JsonResponse({"answer": answer, "tts_audio_base64": tts_audio_base64})
    return JsonResponse({"error": "Invalid request"}, status=400)  # 유효하지 않은 요청에 대해 오류 응답을 반환합니다.


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
