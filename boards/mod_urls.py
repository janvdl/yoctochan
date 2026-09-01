from django.contrib.auth import views as auth_views
from django.urls import path

from . import mod_views


urlpatterns = [
    path(
        "",
        mod_views.dashboard,
        name="mod-dashboard",
    ),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="mod/login.html"),
        name="mod-login",
    ),
    path(
        "logout/",
        auth_views.LogoutView.as_view(),
        name="mod-logout",
    ),
    path(
        "post/<int:post_id>/<str:action>/",
        mod_views.post_action,
        name="mod-post-action",
    ),
    path(
        "thread/<int:thread_id>/<str:action>/",
        mod_views.thread_action,
        name="mod-thread-action",
    ),
    path(
        "reports/",
        mod_views.reports,
        name="mod-reports",
    ),
    path(
        "reports/<int:report_id>/resolve/",
        mod_views.report_resolve,
        name="mod-report-resolve",
    ),
    path(
        "bans/",
        mod_views.bans,
        name="mod-bans",
    ),
    path(
        "bans/create/",
        mod_views.ban_create,
        name="mod-ban-create",
    ),
    path(
        "bans/<int:ban_id>/lift/",
        mod_views.ban_lift,
        name="mod-ban-lift",
    ),
]
