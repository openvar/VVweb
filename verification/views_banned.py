# verification/views_banned.py

from django.shortcuts import render

def banned_landing(request):
    user = request.user
    profile = getattr(user, "profile", None)
    return render(request, "banned.html", {
        "profile": profile,
        "user_obj": user,
        "is_authenticated": user.is_authenticated,
    })