import random
import string


def random_user_name():
    length = 10
    return "".join(random.choice(string.ascii_uppercase) for _ in range(length))
