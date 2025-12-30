import math

from django.contrib import admin
from django import forms
from django.utils.html import mark_safe

from books.models import Book, BookLlm, Image, BookFile


class ImageInlineForm(forms.ModelForm):
    class Meta:
        model = Image
        fields = '__all__'
        widgets = {
            # 'raw_reference_text': forms.Textarea(attrs={'rows': 3, 'cols': 70}),
            # 'target_article_doi': forms.TextInput(attrs={'size': 50}),
            # 'manual_data_json': forms.Textarea(attrs={'rows': 3, 'cols': 70}),
            'image_prompt': forms.Textarea(attrs={'rows': 4, 'cols': 50}),
        }



class ImageInline(admin.TabularInline):
    model = Image
    extra = 0
    classes = ['collapse']
    fields = ('resize_illustration', 'illustration', 'image_prompt')
    readonly_fields = ['resize_illustration']
    # fk_name = 'source_article' # Явно указываем ForeignKey на Article
    form = ImageInlineForm

    def resize_illustration(self, obj):
        if obj.illustration:
            width = obj.illustration.width
            height = obj.illustration.height
            max_size = max(width, height)
            if max_size > 100:
                proportion_side = math.ceil(max_size / 100)
                width = width / proportion_side
                height = height / proportion_side
            return mark_safe(f'<img src="{obj.illustration.url}" width="{width}" height={height} />')
        return None
    resize_illustration.short_description = 'Image'


class BookFileInline(admin.TabularInline):
    model = BookFile
    extra = 0


class BookLlmInline(admin.StackedInline):
    model = BookLlm
    extra = 0


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ['pk', 'book_title', 'author']
    inlines = [BookLlmInline, BookFileInline, ImageInline]

    def book_title(self, obj):
        return f'{obj.title[:30]}...' if len(obj.title) > 30 else obj.title
    book_title.short_description = 'Book Title'


@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ['pk', 'thumb_photo', 'book_title', 'title']
    fields = ('status', 'title', 'book', 'resize_illustration', 'illustration', 'image_prompt', 'created', 'modified')
    readonly_fields = ['created', 'modified', 'resize_illustration']

    def book_title(self, obj):
        return f'{obj.book.title[:30]}...' if len(obj.book.title) > 30 else obj.book.title
    book_title.short_description = 'Book Title'

    def thumb_photo(self, obj):
        if obj.illustration:
            return mark_safe(f'<img src="{obj.illustration.url}" width="100">')
        return '-' * 10
    thumb_photo.short_description = 'Preview'

    def resize_illustration(self, obj):
        if obj.illustration:
            width = obj.illustration.width
            height = obj.illustration.height
            max_size = max(width, height)
            if max_size > 500:
                proportion_side = math.ceil(max_size / 500)
                width = width / proportion_side
                height = height / proportion_side
            return mark_safe(f'<img src="{obj.illustration.url}" width="{width}" height={height} />')
        return None
    resize_illustration.short_description = 'Image'


@admin.register(BookFile)
class BookFileAdmin(admin.ModelAdmin):
    list_display = ['pk', 'book_title']

    def book_title(self, obj):
        return f'{obj.book.title[:30]}...' if len(obj.book.title) > 30 else obj.book.title
    book_title.short_description = 'Book Title'


@admin.register(BookLlm)
class BookLlmAdmin(admin.ModelAdmin):
    list_display = ['pk', 'book_title']

    def book_title(self, obj):
        return f'{obj.book.title[:30]}...' if len(obj.book.title) > 30 else obj.book.title
    book_title.short_description = 'Book Title'