from django.contrib.auth.models import AnonymousUser

def account_status(request):
    user = request.user

    if isinstance(user, AnonymousUser) or not user.is_authenticated:
        return {
            "vv_plan": None,
            "vv_quota_remaining": None,
            "vv_quota_total": None,
        }

    # Your quota model may differ — adjust these fields accordingly.
    quota = getattr(user, "variant_quota", None)

    if quota is None:
        return {
            "vv_plan": "Free Tier",
            "vv_quota_remaining": None,
            "vv_quota_total": None,
        }

    return {
        "vv_plan": getattr(quota, "plan_name", "Free Tier"),
        "vv_quota_remaining": getattr(quota, "effective_allowance_remaining", None),
        "vv_quota_total": getattr(quota, "effective_allowance", None),
    }

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
