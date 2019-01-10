import random
import string


def join_url(*args):
    return "/".join(s.strip("/") for s in args)


def api_url(*args):
    return join_url("/api/v1", *args)


def random_user_name():
    length = 10
    return "".join(random.choice(string.ascii_uppercase) for _ in range(length))