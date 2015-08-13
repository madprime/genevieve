from django.conf.urls import include, url
from django.contrib import admin

from .views import (AuthorizeGennotesView,
                    HomeView,
                    GenomeImportView,
                    GenomeReportDetailView,
                    GenomeReportListView,
                    GenevieveVariantEditView)

urlpatterns = [
    # Examples:
    # url(r'^$', 'genevieve_client.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^$', HomeView.as_view(), name='home'),

    url(r'genome_import/', GenomeImportView.as_view(), name='genome_import'),

    url(r'genome_reports/$', GenomeReportListView.as_view(),
        name='genome_report_list'),
    url(r'genome_report/(?P<pk>[0-9]+)/$', GenomeReportDetailView.as_view(),
        name='genome_report_detail'),

    url(r'variant/(?P<pk>[0-9]+)/$', GenevieveVariantEditView.as_view(),
        name='variant_edit'),

    url(r'authorize_gennotes/', AuthorizeGennotesView.as_view(),
        name='authorize_gennotes'),

    url(r'^admin/', include(admin.site.urls)),

    # django-allauth URLs
    url(r'^accounts/', include('allauth.urls')),
]
