from django.urls import path

from .views import (
    AdminUserListView,
    AssetDetailView,
    AssetListCreateView,
    AttachmentCreateView,
    CategoryListView,
    LoginView,
    LogoutView,
    MeView,
    RecordDetailView,
    RecordListCreateView,
    RecordTypeListView,
)


urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="api_login"),
    path("auth/logout/", LogoutView.as_view(), name="api_logout"),
    path("auth/me/", MeView.as_view(), name="api_me"),
    path("records/", RecordListCreateView.as_view(), name="api_record_list"),
    path("records/<int:pk>/", RecordDetailView.as_view(), name="api_record_detail"),
    path("records/<int:record_id>/attachments/", AttachmentCreateView.as_view(), name="api_attachment_create"),
    path("assets/", AssetListCreateView.as_view(), name="api_asset_list"),
    path("assets/<int:pk>/", AssetDetailView.as_view(), name="api_asset_detail"),
    path("categories/", CategoryListView.as_view(), name="api_category_list"),
    path("record-types/", RecordTypeListView.as_view(), name="api_record_type_list"),
    path("users/", AdminUserListView.as_view(), name="api_user_list"),
]
