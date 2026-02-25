from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress
from allauth.account.utils import send_email_confirmation

User = get_user_model()


def resend_confirmation(request):
    """
    Resend confirmation email WITHOUT requiring login.
    The user's email must be passed in the GET parameter (?email=...),
    which Allauth does on the email-sent page.
    """
    email = request.GET.get("email")

    if not email:
        messages.error(request, "No email address provided.")
        return redirect("account_email_verification_sent")

    try:
        email_obj = EmailAddress.objects.get(email=email)
        user = email_obj.user
    except EmailAddress.DoesNotExist:
        messages.error(request, "Unknown email address.")
        return redirect("account_email_verification_sent")

    send_email_confirmation(request, user)
    messages.success(request, "A new confirmation email has been sent.")

    return redirect("account_email_verification_sent")

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
