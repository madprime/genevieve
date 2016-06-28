from django.conf.urls import include, url
from django.contrib import admin

from .views import (AuthorizeGennotesView,
                    AuthorizeOpenHumansView,
                    CompleteSignupView,
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
    # Examples:
    # url(r'^$', 'genevieve_client.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^$', HomeView.as_view(), name='home'),

    url(r'complete_signup/$', CompleteSignupView.as_view(),
        name='complete_signup'),

    url(r'about/$',
        HomeView.as_view(template_name='genevieve_client/about.html'),
        name='about'),
    url(r'about_notes/$',
        HomeView.as_view(template_name='genevieve_client/about_notes.html'),
        name='about_notes'),

    url(r'public_reports/$',
        PublicGenomeReportListView.as_view(),
        name='public_reports'),

    url(r'genome_import/', GenomeImportView.as_view(), name='genome_import'),

    url(r'genome_reports/$', GenomeReportListView.as_view(),
        name='genome_report_list'),
    url(r'genome_report/reprocess/(?P<pk>[0-9]+)/$',
        GenomeReportReprocessView.as_view(),
        name='genome_report_reprocess'),
    url(r'genome_report/(?P<pk>[0-9]+)/$', GenomeReportDetailView.as_view(),
        name='genome_report_detail'),

    url(r'notes/(?P<pk>[0-9]+)/(?P<relid>[0-9]+)/$',
        GenevieveNotesEditView.as_view(),
        name='notes_edit'),

    url(r'authorize_gennotes/', AuthorizeGennotesView.as_view(),
        name='authorize_gennotes'),
    url(r'authorize_openhumans/', AuthorizeOpenHumansView.as_view(),
        name='authorize_openhumans'),

    url(r'^admin/', include(admin.site.urls)),

    # django-allauth URLs
    url(r'^accounts/', include('allauth.urls')),

    # Account management
    url(r'manage_account/$',
        ManageAccountView.as_view(),
        name='manage_account'),
    url(r'^delete_account/', DeleteAccountView.as_view(), name='delete_account'),
]
