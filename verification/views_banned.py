from django.shortcuts import render

def banned_landing(request):
    return render(request, "banned.html", {"profile": request.user.profile})