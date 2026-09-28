from django.urls import path

from . import controllers


urlpatterns = [
    path("avaliacoes/", controllers.avaliacao_list, name="avaliacao_list"),
    path("avaliacoes/<int:pk>/", controllers.avaliacao_detail, name="avaliacao_detail"),
    path("evidencias/<int:pk>/download/", controllers.evidencia_download, name="evidencia_download"),
]
