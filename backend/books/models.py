from django.db import models
from main.models import Date, Common, PathAndRename


class Book(Date):
    title = models.CharField(verbose_name="Название книги", max_length=255, blank=True)
    author = models.CharField(verbose_name="Автор/Авторы книги", max_length=255, blank=True)
    text = models.TextField(verbose_name="Содержание книги")

    def __str__(self):
        return f'id:{self.id}, title:{self.title}'


class BookLlm(Common):
    book = models.ForeignKey(
        to=Book,
        related_name='llm_texts',
        on_delete=models.CASCADE,
        verbose_name="Book",
    )
    text = models.TextField(
        verbose_name="Структурированный текст книги",
        help_text='Структурированный текст книги созданный LLM',
    )

    def __str__(self):
        return f'id:{self.id}'


class Image(Common):
    title = models.CharField(verbose_name="Название иллюстрации", max_length=255, blank=True)
    book = models.ForeignKey(
        to=Book,
        related_name='images',
        on_delete=models.CASCADE,
        verbose_name="Book",
    )
    illustration = models.ImageField(
        verbose_name='Illustration',
        upload_to=PathAndRename('books/image/illustration'),
        # help_text='Max size 800x800px. JPG',
        # null=True,
        # blank=True,
    )
    image_prompt =  models.CharField(
        verbose_name="Illustration prompt",
        max_length=2000,
        blank=True
    )

    def __str__(self):
        return f'id:{self.id}'


class BookFile(Common):
    book = models.ForeignKey(
        to=Book,
        related_name='files',
        on_delete=models.CASCADE,
        verbose_name="Book",
    )
    file = models.FileField(
        upload_to=PathAndRename('books/book_file/file'),
        verbose_name='Book file',
        max_length=500,
        blank=True,
        null=True,
    )

    def __str__(self):
        return f'id:{self.id}, title:{self.book.title}'