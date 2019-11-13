
def show_user(user):
    if user.first_name and user.last_name:
        return "%s %s" % (user.first_name, user.last_name)
    elif user.first_name:
        return user.first_name
    else:
        return user.username
