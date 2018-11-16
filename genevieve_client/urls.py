from django.conf.urls import include
from django.contrib import admin
from django.urls import path, re_path


from .views import (AuthorizeGennotesView,
                    AuthorizeOpenHumansView,
                    DeleteAccountView,
                    HomeView,
                    GenomeImportView,
                    GenomeReportDetailView,
                    GenomeReportListView,
                    GenomeReportReprocessView,
                    GenevieveNotesEditView,
                    ManageAccountView,
                    PublicGenomeReportListView)

urlpatterns = [
    path('', HomeView.as_view(), name='home'),

    path(r'about/',
         HomeView.as_view(template_name='genevieve_client/about.html'),
         name='about'),
    path(r'about_notes/',
         HomeView.as_view(template_name='genevieve_client/about_notes.html'),
         name='about_notes'),
    path('terms/',
         HomeView.as_view(template_name='genevieve_client/terms.html'),
         name='terms'),

    path('public_reports/',
         PublicGenomeReportListView.as_view(),
         name='public_reports'),

    path('genome_import/', GenomeImportView.as_view(), name='genome_import'),

    path('genome_reports/', GenomeReportListView.as_view(),
         name='genome_report_list'),
    re_path('genome_report/reprocess/(?P<pk>[0-9]+)/',
         GenomeReportReprocessView.as_view(),
         name='genome_report_reprocess'),
    re_path('genome_report/(?P<pk>[0-9]+)/', GenomeReportDetailView.as_view(),
         name='genome_report_detail'),

    re_path('notes/(?P<pk>[0-9]+)/(?P<relid>[0-9]+)/',
         GenevieveNotesEditView.as_view(),
         name='notes_edit'),

    path('authorize_gennotes/', AuthorizeGennotesView.as_view(),
         name='authorize_gennotes'),
    path(r'authorize_openhumans/', AuthorizeOpenHumansView.as_view(),
         name='authorize_openhumans'),

    path('admin/', admin.site.urls),

    # django-allauth URLs
    path(r'accounts/', include('allauth.urls')),

    # Account management
    path('manage_account/',
         ManageAccountView.as_view(),
         name='manage_account'),
    path('delete_account/', DeleteAccountView.as_view(),
         name='delete_account'),
]
