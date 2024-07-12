import os

from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

User = get_user_model()

# Create your models here.


def upload_to(instance, filename):
    # Split the file name and extension
    base, ext = os.path.splitext(filename)
    # Generate the new file name with the primary key
    if instance.id:
        new_filename = f"{base}_{instance.id}{ext}"
    else:
        new_filename = f"{base}_tmp{ext}"
    return os.path.join("record/videos/", new_filename)


class Condition(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    condition_date = models.DateField(auto_now_add=True)
    condition_time = models.TimeField(auto_now_add=True)
    condition_image = models.ImageField(upload_to="record/images/")
    condition_location = models.TextField(null=False)


class Accident(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    accident_date = models.DateField(auto_now_add=True)
    accident_time = models.TimeField(auto_now_add=True)
    accident_video = models.FileField(upload_to=upload_to)
    accident_location = models.TextField(null=False)

    def save(self, *args, **kwargs):
        # Check if the instance is new by checking if it has an id
        is_new = self._state.adding
        temp_video_file = self.accident_video

        # Temporarily save the file to a temporary location
        self.accident_video = None
        super().save(*args, **kwargs)

        if is_new:
            # Rename the file with the primary key
            new_file_name = upload_to(self, temp_video_file.name)
            self.accident_video = temp_video_file
            self.accident_video.name = new_file_name
            # Save again to update the file path
            super().save(update_fields=["accident_video"])
        else:
            super().save(*args, **kwargs)


# Signal handlers


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
