from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

class Contact(models.Model):
    nameval = models.CharField(max_length=100, verbose_name='Name')
    emailval = models.EmailField(verbose_name='Email')
    variant = models.CharField(max_length=100, null=True, blank=True)
    question = models.TextField()
    asked = models.DateTimeField(default=timezone.now)
    answered = models.BooleanField(default=False)

    def __str__(self):
        return "%s - %s (dealt with: %s)" % (self.nameval, self.asked.date(), self.answered)


class VariantQuota(models.Model):
    """
    Tracks monthly variant submissions per user.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='variant_quota')
    count = models.PositiveIntegerField(default=0)
    max_allowance = models.PositiveIntegerField(default=getattr(settings, "DEFAULT_MONTHLY_VARIANT_ALLOWANCE", 20000))
    last_reset = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} quota: {self.count}/{self.max_allowance}"

    def get_now(self):
        return timezone.now()

    def reset_if_needed(self):
        """
        Resets count if more than 30 days since last_reset.
        """
        if self.last_reset + timedelta(days=30) <= self.get_now():
            self.count = 0
            self.last_reset = self.get_now()
            self.save()

    def remaining(self):
        self.reset_if_needed()
        return max(self.max_allowance - self.count, 0)

    def add_variants(self, n):
        """
        Safely add n variants to the count.
        """
        self.reset_if_needed()
        if self.count + n > self.max_allowance:
            raise ValueError("Monthly allowance exceeded")
        self.count += n
        self.save()

# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# </LICENSE>
