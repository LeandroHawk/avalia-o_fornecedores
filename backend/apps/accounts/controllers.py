from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy


class AppLoginView(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def get_default_redirect_url(self):
        return reverse_lazy("avaliacao_list")
