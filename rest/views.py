from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, rest
from .serializers import UserSerializer, RegisterSerializer, RestSerializer
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser


# ============================================
# AUTH
# ============================================
@api_view(["POST"])
@permission_classes([AllowAny])
def register_view(request):
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "Muvaffaqiyatli ro'yxatdan o'tdingiz!"},
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    """Login — username + password orqali"""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")

    if not username or not password:
        return Response(
            {"error": "Username va parolni kiriting!"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Bloklangan tekshirish
    try:
        user_obj = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response(
            {"error": "Username yoki parol noto'g'ri!"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if user_obj.is_blocked:
        return Response(
            {"error": "Akkauntingiz bloklangan!"}, status=status.HTTP_403_FORBIDDEN
        )

    # Parolni tekshirish
    user = authenticate(username=username, password=password)
    if user is None:
        return Response(
            {"error": "Username yoki parol noto'g'ri!"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # Token yaratish
    refresh = RefreshToken.for_user(user)
    role = "admin" if user.is_superuser else "customer"

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "role": role,
            "user": UserSerializer(user).data,
        }
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def admin_login_view(request):
    """Admin login — username + password"""
    username = request.data.get("username", "").strip()
    password = request.data.get("password", "")

    if not username or not password:
        return Response(
            {"error": "Username va parolni kiriting!"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user_obj = User.objects.get(username=username)
    except User.DoesNotExist:
        return Response(
            {"error": "Username yoki parol noto'g'ri!"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not user_obj.is_superuser:
        return Response(
            {"error": "Siz admin emassiz!"}, status=status.HTTP_403_FORBIDDEN
        )

    if user_obj.is_blocked:
        return Response(
            {"error": "Akkauntingiz bloklangan!"}, status=status.HTTP_403_FORBIDDEN
        )

    user = authenticate(username=username, password=password)
    if user is None:
        return Response(
            {"error": "Username yoki parol noto'g'ri!"},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    refresh = RefreshToken.for_user(user)

    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "role": "admin",
            "user": UserSerializer(user).data,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):
    return Response(UserSerializer(request.user).data)


# ============================================
# STATS
# ============================================
@api_view(["GET"])
@permission_classes([AllowAny])
def stats_view(request):
    return Response(
        {
            "total_users": User.objects.count(),
            "total_products": rest.objects.count(),
            "sold_products": 0,
            "total_revenue": 0,
        }
    )


# ============================================
# USERS CRUD
# ============================================
@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def users_view(request):
    """Foydalanuvchilar ro'yxati + yangi qo'shish"""
    if request.method == "GET":
        users = User.objects.all().order_by("-date_joined")
        return Response(UserSerializer(users, many=True).data)

    elif request.method == "POST":
        # ✅ Ma'lumotlarni tayyorlash
        data = request.data.copy()

        # Username — agar yo'q bo'lsa email'dan olinadi
        if not data.get("username"):
            email = data.get("email", "")
            if email:
                data["username"] = email.split("@")[0]
            else:
                return Response(
                    {"error": "Email majburiy!"}, status=status.HTTP_400_BAD_REQUEST
                )

        # ✅ Email bandligini tekshirish
        if User.objects.filter(email=data.get("email")).exists():
            return Response(
                {"error": "Bu email allaqachon band!"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ✅ Username unikalligini tekshirish
        base_username = data["username"]
        counter = 1
        while User.objects.filter(username=data["username"]).exists():
            data["username"] = f"{base_username}{counter}"
            counter += 1

        # ✅ Parolni tekshirish
        if not data.get("password"):
            return Response(
                {"error": "Parol majburiy!"}, status=status.HTTP_400_BAD_REQUEST
            )

        serializer = UserSerializer(data=data)
        if serializer.is_valid():
            user = serializer.save()
            return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "DELETE"])
@permission_classes([AllowAny])
def user_detail_view(request, user_id):
    """Bitta user bilan ishlash"""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"error": "Foydalanuvchi topilmadi"}, status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        return Response(UserSerializer(user).data)

    elif request.method == "PUT":
        serializer = UserSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        if request.user.is_authenticated and user.id == request.user.id:
            return Response(
                {"error": "O'zingizni o'chira olmaysiz!"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.delete()
        return Response({"message": "O'chirildi"}, status=status.HTTP_204_NO_CONTENT)


@api_view(["POST"])
@permission_classes([AllowAny])
def toggle_block_view(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "Topilmadi"}, status=status.HTTP_404_NOT_FOUND)

    user.is_blocked = not user.is_blocked
    user.save()
    return Response(UserSerializer(user).data)


# ============================================
# MAHSULOTLAR API
# ============================================


class RestListCreateView(generics.ListCreateAPIView):
    """
    GET  /api/rest/  → barcha mahsulotlar
    POST /api/rest/  → yangi mahsulot qo'shish
    """

    queryset = rest.objects.all().order_by("-yaratilgan")
    serializer_class = RestSerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_context(self):
        return {"request": self.request}


class RestDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET    /api/rest/<id>/  → mahsulot ko'rish
    PUT    /api/rest/<id>/  → to'liq yangilash
    PATCH  /api/rest/<id>/  → qismiy yangilash
    DELETE /api/rest/<id>/  → o'chirish
    """

    queryset = rest.objects.all()
    serializer_class = RestSerializer
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_serializer_context(self):
        return {"request": self.request}
