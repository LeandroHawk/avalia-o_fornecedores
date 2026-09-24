"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from apps import api
from apps.avaliacoes import views as avaliacao_views
from apps.core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", core_views.home, name="home"),
    path("login/", auth_views.LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", core_views.dashboard, name="dashboard"),
    path("pendencias/", core_views.central_pendencias, name="pendencias"),
    path("avaliacoes/", avaliacao_views.avaliacao_list, name="avaliacao_list"),
    path("avaliacoes/<int:pk>/", avaliacao_views.avaliacao_detail, name="avaliacao_detail"),
    path("avaliacoes/<int:pk>/questoes/<int:questao_id>/", avaliacao_views.responder_questao, name="responder_questao"),
    path("avaliacoes/<int:pk>/enviar/", avaliacao_views.enviar, name="avaliacao_enviar"),
    path("avaliacoes/<int:pk>/iniciar-analise/", avaliacao_views.iniciar_analise_view, name="avaliacao_iniciar_analise"),
    path("avaliacoes/<int:pk>/devolver/", avaliacao_views.devolver, name="avaliacao_devolver"),
    path("avaliacoes/<int:pk>/iniciar-correcao/", avaliacao_views.iniciar_correcao_view, name="avaliacao_iniciar_correcao"),
    path("avaliacoes/<int:pk>/finalizar/", avaliacao_views.finalizar, name="avaliacao_finalizar"),
    path("evidencias/<int:pk>/download/", avaliacao_views.evidencia_download, name="evidencia_download"),
    path("api/v1/", include(api.router.urls)),
]
