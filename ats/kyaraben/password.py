
import random
import string


def generate_password(size, password_chars=string.ascii_letters + string.digits):
    chars = []
    while len(chars) < size:
        chars.append(random.SystemRandom().choice(password_chars))
    return ''.join(chars)
