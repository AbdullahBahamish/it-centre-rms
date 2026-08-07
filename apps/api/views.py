from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.services import AccessService
from apps.records.domain.uploads import validate_upload
from apps.records.models import Category, ITAsset, Record, RecordAttachment, RecordType

from .permissions import AdminPermission, AssetPermission, RMSPermission
from .authentication import ExpiringTokenAuthentication
from .serializers import (
    CategorySerializer,
    ITAssetSerializer,
    RecordAttachmentSerializer,
    RecordSerializer,
    RecordTypeSerializer,
    UserSerializer,
)


User = get_user_model()


class LoginView(ObtainAuthToken):
    """Issue a revocable token. Use only over HTTPS in production."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return response
        token = Token.objects.get(key=response.data["token"])
        user = token.user
        Token.objects.filter(user=user).exclude(pk=token.pk).delete()
        token.delete()
        token = Token.objects.create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def post(self, request):
        request.auth.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class RecordListCreateView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (RMSPermission,)
    parser_classes = (JSONParser,)

    def get(self, request):
        records = [record for record in Record.objects.select_related("category", "record_type", "created_by").prefetch_related("attachments") if AccessService.can(request.user, "view_record", record)]
        return Response(RecordSerializer(records, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = RecordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(RecordSerializer(record, context={"request": request}).data, status=status.HTTP_201_CREATED)


class RecordDetailView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (RMSPermission,)
    parser_classes = (JSONParser,)

    def get_object(self, request, pk):
        record = get_object_or_404(Record.objects.select_related("category", "record_type", "created_by"), pk=pk)
        self.check_object_permissions(request, record)
        return record

    def get(self, request, pk):
        return Response(RecordSerializer(self.get_object(request, pk), context={"request": request}).data)

    def put(self, request, pk):
        return self._update(request, pk, partial=False)

    def patch(self, request, pk):
        return self._update(request, pk, partial=True)

    def _update(self, request, pk, partial):
        record = self.get_object(request, pk)
        serializer = RecordSerializer(record, data=request.data, partial=partial, context={"request": request})
        serializer.is_valid(raise_exception=True)
        record = serializer.save()
        return Response(RecordSerializer(record, context={"request": request}).data)

    def delete(self, request, pk):
        record = self.get_object(request, pk)
        record.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssetListCreateView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (AssetPermission,)
    parser_classes = (JSONParser,)

    def get(self, request):
        return Response(ITAssetSerializer(ITAsset.objects.all(), many=True).data)

    def post(self, request):
        serializer = ITAssetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AssetDetailView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (AssetPermission,)
    parser_classes = (JSONParser,)

    def get_object(self, request, pk):
        asset = get_object_or_404(ITAsset, pk=pk)
        self.check_object_permissions(request, asset)
        return asset

    def get(self, request, pk):
        return Response(ITAssetSerializer(self.get_object(request, pk)).data)

    def patch(self, request, pk):
        asset = self.get_object(request, pk)
        serializer = ITAssetSerializer(asset, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(ITAssetSerializer(serializer.save()).data)

    def delete(self, request, pk):
        self.get_object(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CategoryListView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        categories = [category for category in Category.objects.all() if AccessService.can(request.user, "access_category", category)]
        return Response(CategorySerializer(categories, many=True).data)


class RecordTypeListView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get(self, request):
        return Response(RecordTypeSerializer(RecordType.objects.all(), many=True).data)


class AttachmentCreateView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (IsAuthenticated,)
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request, record_id):
        record = get_object_or_404(Record, pk=record_id)
        if not AccessService.can(request.user, "update_record", record):
            return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
        upload = request.FILES.get("file")
        if not upload:
            return Response({"file": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_upload(upload)
        except ValidationError as exc:
            return Response({"file": exc.messages}, status=status.HTTP_400_BAD_REQUEST)
        attachment = RecordAttachment.objects.create(record=record, file=upload)
        return Response(RecordAttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)


class AdminUserListView(APIView):
    authentication_classes = (ExpiringTokenAuthentication,)
    permission_classes = (AdminPermission,)

    def get(self, request):
        return Response(UserSerializer(User.objects.select_related("userprofile__role").order_by("username"), many=True).data)
