from django.urls import path

from . import controllers


urlpatterns = [
    path("", controllers.home, name="home"),
    path("dashboard/", controllers.dashboard, name="dashboard"),
    path("pendencias/", controllers.central_pendencias, name="pendencias"),
]
