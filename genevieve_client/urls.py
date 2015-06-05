from django.conf.urls import include, url
from django.contrib import admin
from django.views.generic import TemplateView

from .views import GenomeImportView, GenomeReportListView

urlpatterns = [
    # Examples:
    # url(r'^$', 'genevieve_client.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^$',
        TemplateView.as_view(template_name='genevieve_client/home.html'),
        name='home'),
    url(r'genome_import/', GenomeImportView.as_view(), name='genome_import'),
    url(r'genome_reports/$', GenomeReportListView.as_view(),
        name='genome_reports'),

    url(r'^admin/', include(admin.site.urls)),

    # django-allauth URLs
    url(r'^accounts/', include('allauth.urls')),
]
