from django.urls import path

from . import api_views

app_name = "crm_api"

urlpatterns = [
    path("stages/", api_views.StageListApiView.as_view(), name="stage-list"),
    path("contacts/", api_views.ContactListApiView.as_view(), name="contact-list"),
    path("contacts/<int:pk>/", api_views.ContactDetailApiView.as_view(), name="contact-detail"),
    path("deals/", api_views.DealListApiView.as_view(), name="deal-list"),
    path("deals/<int:pk>/", api_views.DealDetailApiView.as_view(), name="deal-detail"),
    path("deals/<int:pk>/notes/", api_views.DealNoteApiView.as_view(), name="deal-add-note"),
    path(
        "deals/<int:pk>/contacts/",
        api_views.DealContactLinkApiView.as_view(),
        name="deal-add-contact",
    ),
    path(
        "deals/<int:pk>/contacts/<int:contact_pk>/",
        api_views.DealContactDetailApiView.as_view(),
        name="deal-remove-contact",
    ),
]
