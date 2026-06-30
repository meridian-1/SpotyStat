from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import generics, permissions, status
from .serializers import UserProfileSerializer, UserUpdateSerializer


class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ["PUT", "PATCH"]:
            return UserUpdateSerializer
        return UserProfileSerializer
