import os
import json
import time
# from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image as PILImage
import io
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.pagesizes import letter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from django.conf import settings
from django.http import FileResponse
from rest_framework import viewsets, status
from rest_framework.response import Response

from .models import Book, BookLlm, BookFile, Image
from .serializers import BookSerializer


# # Заглушка для работы с LLM (Google Gemini)
# def process_book_with_llm(title, author, text):
#     """
#     Заглушка функции, которая в будущем будет отправлять данные в Gemini.
#     Возвращает фиктивные иллюстрации и размеченный текст.
#     """
#     print(f"Обработка книги: {title} от {author}")

#     # Имитация добавления меток для иллюстраций
#     marked_text = text.replace(".", ".\n[ILLUSTRATION_HERE]\n", 2)

#     illustrations = [
#         {"id": 1, "url": "https://via.placeholder.com/400x300?text=Illustration+1"},
#         {"id": 2, "url": "https://via.placeholder.com/400x300?text=Illustration+2"}
#     ]

#     return {
#         "marked_text": marked_text,
#         "illustrations": illustrations
#     }


client = genai.Client(api_key=settings.GEMINI_API_KEY)


def get_book_content_with_markers(text):
    """
    Отправляет текст в Gemini и получает структурированный список блоков (текст и промпты для иллюстраций).
    """
    print("🚀 Анализируем текст книги и расставляем метки для иллюстраций...")

    prompt = f"""
    Проанализируй следующий текст и преврати его в структуру для иллюстрированной книги.
    Раздели текст на логические части. Между частями текста добавь описания для иллюстраций, которые лучше всего подходят к этому моменту.

    Верни ответ ТОЛЬКО в формате JSON:
    {{
      "title": "Название книги",
      "author": "Автор",
      "content": [
        {{"type": "text", "data": "Кусочек текста..."}},
        {{"type": "image_prompt", "data": "Подробное описание того, что должно быть на картинке для этого момента..."}},
        {{"type": "text", "data": "Следующий кусочек текста..."}}
      ]
    }}

    Сделай как минимум 5-7 иллюстраций для этой книги. Описания для картинок (image_prompt) должны быть на английском языке для лучшей генерации.

    Текст:
    {text}
    """

    # Пробуем доступные модели
    models_to_try = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]

    for model_name in models_to_try:
        try:
            print(f"  - Используем модель {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.7
                )
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"  ⚠️ Ошибка с {model_name}: {e}")
            if "429" in str(e):
                print("  ⌛ Лимит исчерпан, ждем 10 секунд...")
                time.sleep(10)
            else:
                continue

    raise Exception("Не удалось получить ответ ни от одной из моделей Gemini.")


def generate_images(book_data):
    """
    Проходит по контенту, находит image_prompt и генерирует изображения.
    """
    print("🎨 Генерируем иллюстрации...")

    if not os.path.exists("images"):
        os.makedirs("images")

    image_count = 0
    for item in book_data.get("content", []):
        if item["type"] == "image_prompt":
            prompt = item["data"]
            image_count += 1
            print(f"  - Генерация картинки {image_count}: {prompt[:50]}...")

            # Пробуем несколько моделей для генерации изображений
            image_models = ["imagen-3.0-generate-001", "imagen-4.0-generate-001"]
            success = False

            for img_model in image_models:
                try:
                    print(f"    - Пробуем {img_model}...")
                    resp_alt = client.models.generate_content(
                        model=img_model,
                        contents=prompt
                    )
                    if resp_alt.candidates and resp_alt.candidates[0].content.parts:
                        for part in resp_alt.candidates[0].content.parts:
                            if part.inline_data:
                                image_bytes = part.inline_data.data
                                image = PILImage.open(io.BytesIO(image_bytes))
                                image_path = f"images/gen_{image_count}.png"
                                image.save(image_path)
                                item["image_path"] = image_path
                                print(f"    ✅ Сохранено (multimodal): {image_path}")
                                success = True
                                break
                except Exception as e:
                    print(f"    ❌ Ошибка с {img_model}: {e}")

            if not success:
                # Попытка через gemini-2.0-flash-exp-image-generation
                try:
                    print("    - Пробуем gemini-2.0-flash-exp-image-generation...")
                    resp_alt = client.models.generate_content(
                        model="gemini-2.0-flash-exp-image-generation",
                        contents=prompt
                    )
                    if resp_alt.candidates and resp_alt.candidates[0].content.parts:
                        for part in resp_alt.candidates[0].content.parts:
                            if part.inline_data:
                                image_bytes = part.inline_data.data
                                image = PILImage.open(io.BytesIO(image_bytes))
                                image_path = f"images/gen_{image_count}.png"
                                image.save(image_path)
                                item["image_path"] = image_path
                                print(f"    ✅ Сохранено (multimodal): {image_path}")
                                success = True
                                break
                except Exception as e2:
                    print(f"    ❌ Все попытки генерации провалены.")

    return book_data


def create_pdf(book_data, output_filename="generated_book.pdf"):
    """
    Создает PDF файл на основе полученных данных.
    """
    print(f"📚 Создаем PDF: {output_filename}...")
    doc = SimpleDocTemplate(output_filename, pagesize=letter)
    styles = getSampleStyleSheet()

    # Настройка шрифта
    font_path = "DejaVu_Sans/DejaVuSans.ttf"
    if os.path.exists(font_path):
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        font_name = 'DejaVuSans'
    else:
        font_name = 'Helvetica'

    styles.add(ParagraphStyle(name='BookText', fontName=font_name, fontSize=14, leading=18, spaceAfter=12))
    styles.add(ParagraphStyle(name='BookTitle', fontName=font_name, fontSize=28, alignment=1, spaceAfter=30))
    styles.add(ParagraphStyle(name='BookAuthor', fontName=font_name, fontSize=18, alignment=1, spaceAfter=50))

    story = []

    # Титульная страница
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph(book_data.get("title", "Книга"), styles['BookTitle']))
    story.append(Paragraph(book_data.get("author", ""), styles['BookAuthor']))
    story.append(PageBreak())

    # Основной контент
    for item in book_data.get("content", []):
        if item["type"] == "text":
            text_data = item["data"].replace("\n", "<br/>")
            story.append(Paragraph(text_data, styles['BookText']))
        elif item["type"] == "image_prompt" and "image_path" in item:
            img_path = item["image_path"]
            if os.path.exists(img_path):
                img = RLImage(img_path, width=5.5*inch, height=5.5*inch, kind='proportional')
                story.append(img)
                story.append(Spacer(1, 12))

    doc.build(story)
    print(f"✨ PDF готов: {output_filename}")


class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        book = serializer.instance

        try:
            print("Step 1: Getting book content with markers")
            # 1. Получаем структуру
            book_data = get_book_content_with_markers(book.text)
            BookLlm.objects.create(book=book, text=json.dumps(book_data, ensure_ascii=False, indent=2))
            print("Step 1 finished")

            print("Step 2: Using test images")
            # 2. Используем тестовые картинки
            test_images_dir = 'test_images'
            image_paths = [os.path.join(test_images_dir, f) for f in os.listdir(test_images_dir) if f.endswith(('.png', '.jpg', '.jpeg'))]
            print(f"Found {len(image_paths)} test images.")

            image_index = 0
            for item in book_data.get("content", []):
                if item["type"] == "image_prompt":
                    if image_index < len(image_paths):
                        image_path = image_paths[image_index]
                        item["image_path"] = image_path
                        Image.objects.create(book=book, image_prompt=item["data"], illustration=image_path)
                        image_index += 1
            print("Step 2 finished")

            print("Step 3: Creating PDF")
            # 3. Создаем PDF
            pdf_filename = f"generated_book_{book.id}.pdf"
            create_pdf(book_data, pdf_filename)
            print("Step 3 finished")

            print("Step 4: Saving PDF to model")
            # 4. Сохраняем PDF в модель
            pdf_path = os.path.join(settings.BASE_DIR, pdf_filename)
            if os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    book_file = BookFile(book=book)
                    book_file.file.save(pdf_filename, f)
                    book_file.save()
                print("Step 4 finished")

                print("Step 5: Returning PDF")
                # 5. Отдаем PDF
                response = FileResponse(open(pdf_path, 'rb'), as_attachment=True, filename=pdf_filename)
                return response
            else:
                print("Error: PDF file not found.")
                return Response({"error": "PDF file not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            print(f"An error occurred: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
