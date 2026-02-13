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

    PLAN_CHOICES = [
        ("standard", "Standard"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)

    plan = models.CharField(
        max_length=20,
        choices=PLAN_CHOICES,
        default="standard"
    )

    subscription_expires = models.DateTimeField(null=True, blank=True)

    count = models.PositiveIntegerField(default=0)
    last_reset = models.DateTimeField(default=timezone.now)

    custom_limit = models.PositiveIntegerField(null=True, blank=True)

    # -----------------------------
    # PLAN / LIMIT LOGIC
    # -----------------------------

    @property
    def max_allowance(self):

        if self.custom_limit is not None:
            return self.custom_limit

        if self.plan == "standard":
            return settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE

        if self.plan == "pro":
            return settings.PRO_LIMIT

        if self.plan == "enterprise":
            return settings.ENTERPRISE_LIMIT

        return settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE


    # -----------------------------
    # SUBSCRIPTION CHECK
    # -----------------------------

    def check_subscription_status(self):

        if (
            self.plan != "standard"
            and self.subscription_expires
            and timezone.now() >= self.subscription_expires
        ):
            self.plan = "standard"
            self.subscription_expires = None
            self.count = 0
            self.last_reset = timezone.now()
            self.save()


    # -----------------------------
    # MONTHLY RESET
    # -----------------------------

    def reset_if_needed(self):
        if self.last_reset + timedelta(days=30) <= timezone.now():
            self.count = 0
            self.last_reset = timezone.now()
            # clear temporary custom limit
            self.custom_limit = None
            self.save()

    # -----------------------------
    # PUBLIC App
    # -----------------------------

    def remaining(self):
        self.check_subscription_status()
        self.reset_if_needed()
        return max(self.max_allowance - self.count, 0)


    def add_variants(self, n):
        self.check_subscription_status()
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
