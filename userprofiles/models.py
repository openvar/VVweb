from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import ugettext_lazy as _


JOBS = (
    ('clinician', 'Clinician'),
    ('researcher', 'Researcher'),
    ('bioinformatician', 'Bioinformatician'),
    ('student', 'Student'),
    ('other', 'Other'),
)

COUNTRIES = (
    ('UK', 'United Kingdom'),
    ('IE', 'Ireland'),
    ('US', 'United States of America'),
    ('FR', 'France'),
    ('NA', 'Other')
)


class UserProfile(models.Model):
    user = models.OneToOneField(User, null=True, related_name="profile",
                                verbose_name=_('User'), on_delete=models.CASCADE)
    institution = models.CharField(
        max_length=150, null=True, blank=True, verbose_name=_('Institution'))
    country = models.CharField(
        max_length=2, blank=True, verbose_name=_('Country'), choices=COUNTRIES
    )
    jobrole = models.CharField(
        max_length=140, blank=True, verbose_name=_('Job Role/Interest'), choices=JOBS)

    completion_level = models.PositiveSmallIntegerField(
        default=0, verbose_name=_('Profile completion percentage'))
    email_is_verified = models.BooleanField(
        default=False, verbose_name=_('Email is verified'))
    personal_info_is_completed = models.BooleanField(
        default=False, verbose_name=_('Personal info completed'))

    class Meta:
        verbose_name = _('User profile')
        verbose_name_plural = _('User profiles')

    def __str__(self):
        return "User profile: %s" % self.user.username

    def get_completion_level(self):
        completion_level = 0
        if self.email_is_verified:
            completion_level += 50
        if self.personal_info_is_completed:
            completion_level += 50
        return completion_level

    def update_completion_level(self):
        self.completion_level = self.get_completion_level()
        self.save()
