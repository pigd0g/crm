from django.urls import path

from . import views

app_name = "crm"

urlpatterns = [
    path("", views.HomeRedirectView.as_view(), name="home"),
    path("pipeline/", views.PipelineView.as_view(), name="pipeline"),
    path("deals/", views.DealListView.as_view(), name="deal-list"),
    path("deals/new/", views.DealCreateView.as_view(), name="deal-create"),
    path("deals/<int:pk>/", views.DealDetailView.as_view(), name="deal-detail"),
    path("deals/<int:pk>/edit/", views.DealUpdateView.as_view(), name="deal-edit"),
    path("deals/<int:pk>/notes/", views.DealAddNoteView.as_view(), name="deal-add-note"),
    path(
        "deals/<int:pk>/contacts/add/",
        views.DealAddContactView.as_view(),
        name="deal-add-contact",
    ),
    path(
        "deals/<int:pk>/contacts/<int:contact_pk>/remove/",
        views.DealRemoveContactView.as_view(),
        name="deal-remove-contact",
    ),
    path("contacts/", views.ContactListView.as_view(), name="contact-list"),
    path("contacts/import/", views.ContactImportView.as_view(), name="contact-import"),
    path("contacts/new/", views.ContactCreateView.as_view(), name="contact-create"),
    path("contacts/<int:pk>/edit/", views.ContactUpdateView.as_view(), name="contact-edit"),
]
