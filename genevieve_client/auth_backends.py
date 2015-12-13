from django.contrib.auth.backends import ModelBackend


class AuthenticationBackend(ModelBackend):

    def authenticate(self, **credentials):
        return None
