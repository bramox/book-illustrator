from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings


from books.urls import router as books_router

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/books/', include(books_router.urls)),
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
