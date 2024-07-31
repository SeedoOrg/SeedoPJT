import os

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

User = get_user_model()


# 사고기록을 스토리지 내에서 저장해둘 경로
def upload_to(instance, filename):
    # 파일 이름과 확장자 분리
    base, ext = os.path.splitext(filename)

    # 기본 키를 사용하여 새로운 파일 이름 생성
    if instance.id:
        new_filename = f"{base}_{instance.id}{ext}"
    else:
        new_filename = f"{base}_tmp{ext}"
    return os.path.join("record/videos/", new_filename)


# 파손기록을 스토리지 내에서 저장해둘 경로
def upload_to_img(instance, filename):
    # 파일 이름과 확장자 분리
    base, ext = os.path.splitext(filename)

    # 기본 키를 사용하여 새로운 파일 이름 생성
    if instance.id:
        new_filename = f"{base}_{instance.id}{ext}"
    else:
        new_filename = f"{base}_tmp{ext}"
    return os.path.join("record/images/", new_filename)


# 파손된 점자블록 저장할 DB 테이블
class Condition(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    condition_date = models.DateField(auto_now_add=True)
    condition_time = models.TimeField(auto_now_add=True)
    condition_image = models.ImageField(upload_to=upload_to_img)
    condition_location = models.TextField(null=False)

    def save(self, *args, **kwargs):
        # 인스턴스가 새 객체인지 id로 확인
        is_new = self._state.adding
        temp_image_file = self.condition_image

        # 파일을 임시 위치에 저장
        self.condition_image = None
        super().save(*args, **kwargs)

        if is_new:
            # 기본 키로 파일 이름 변경
            new_file_name = upload_to_img(self, temp_image_file.name)
            self.condition_image = temp_image_file
            self.condition_image.name = new_file_name
            # 파일 경로를 업데이트하기 위해 다시 저장
            super().save(update_fields=["condition_image"])
        else:
            super().save(*args, **kwargs)


# 낙상 사고기록 저장할 DB 테이블
class Accident(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    accident_date = models.DateField(auto_now_add=True)
    accident_time = models.TimeField(auto_now_add=True)
    accident_video = models.FileField(upload_to=upload_to)
    accident_location = models.TextField(null=False)

    def save(self, *args, **kwargs):
        # 인스턴스가 새 객체인지 id로 확인
        is_new = self._state.adding
        temp_video_file = self.accident_video

        # 파일을 임시 위치에 저장
        self.accident_video = None
        super().save(*args, **kwargs)

        if is_new:
            # 기본 키로 파일 이름 변경
            new_file_name = upload_to(self, temp_video_file.name)
            self.accident_video = temp_video_file
            self.accident_video.name = new_file_name
            # 파일 경로를 업데이트하기 위해 다시 저장
            super().save(update_fields=["accident_video"])
        else:
            super().save(*args, **kwargs)


# Signal handlers
# 기존 파일이 수정되거나, 삭제될 경우 실제 스토리지에서도 삭제하는 부분


@receiver(pre_save, sender=Condition)
def delete_old_condition_image(sender, instance, **kwargs):
    if instance.pk:
        old_instance = Condition.objects.get(pk=instance.pk)
        if old_instance.condition_image and old_instance.condition_image != instance.condition_image:
            old_instance.condition_image.delete(save=False)


@receiver(post_delete, sender=Condition)
def delete_condition_image_on_delete(sender, instance, **kwargs):
    if instance.condition_image:
        instance.condition_image.delete(save=False)


@receiver(pre_save, sender=Accident)
def delete_old_accident_video(sender, instance, **kwargs):
    if instance.pk:
        old_instance = Accident.objects.get(pk=instance.pk)
        if old_instance.accident_video and old_instance.accident_video != instance.accident_video:
            old_instance.accident_video.delete(save=False)


@receiver(post_delete, sender=Accident)
def delete_accident_video_on_delete(sender, instance, **kwargs):
    if instance.accident_video:
        instance.accident_video.delete(save=False)
