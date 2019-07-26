from django.db import models
from django.utils import timezone


class Contact(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    variant = models.CharField(max_length=100, null=True, blank=True)
    question = models.TextField()
    asked = models.DateTimeField(default=timezone.now)
    answered = models.BooleanField(default=False)

    def __str__(self):
        return "%s - %s (dealt with: %s)" % (self.name, self.asked.date(), self.answered)

    def send_email(self):
        """
        Function will email contact information to admins
        :return:
        """
        print("Sending email")
