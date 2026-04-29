from django.contrib.auth.backends import ModelBackend

class ProfileAwareModelBackend(ModelBackend):
    """
    Deny login when a user's profile is marked banned.
    Works for username/password (allauth still calls through Django auth).
    """

    def user_can_authenticate(self, user):
        can = super().user_can_authenticate(user)
        if not can:
            return False

        # If there's no profile yet, don't block (defensive)
        profile = getattr(user, "profile", None)
        if profile is None:
            return True

        return profile.verification_status != "banned"

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
