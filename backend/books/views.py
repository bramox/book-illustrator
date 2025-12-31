import os
import json
import time
import shutil
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
from django.core.files.base import ContentFile
from django.http import FileResponse
from rest_framework import viewsets, status
from rest_framework.response import Response

from .models import Book, BookLlm, BookFile, Image
from .serializers import BookSerializer


client = genai.Client(api_key=settings.GEMINI_API_KEY)


def get_book_content_with_markers(text):
    """
    Sends text to Gemini and receives a structured list of blocks (text and illustration prompts).
    """
    print("🚀 Analyzing the book text and placing markers for illustrations...")

    prompt = f"""
    Analyze the following text and turn it into a structure for an illustrated book.
    Divide the text into logical parts. Between the parts of the text, add descriptions for illustrations that best fit that moment.

    Return the response ONLY in JSON format:
    {{
      "title": "Book Title",
      "author": "Author",
      "content": [
        {{"type": "text", "data": "A piece of text..."}},
        {{"type": "image_prompt", "data": "A detailed description of what should be in the picture for this moment..."}},
        {{"type": "text", "data": "The next piece of text..."}}
      ]
    }}

    Make at least 5-7 illustrations for this book. The descriptions for the images (image_prompt) should be in English for better generation.

    Text:
    {text}
    """

    # Trying available models
    models_to_try = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]

    for model_name in models_to_try:
        try:
            print(f"  - We use the model {model_name}...")
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
            print(f"  ⚠️ Error with {model_name}: {e}")
            if "429" in str(e):
                print("  ⌛ Limit reached, wait 10 seconds...")
                time.sleep(10)
            else:
                continue

    raise Exception("Unable to get a response from any of the Gemini models.")


def generate_images(book, book_data):
    """
    Iterates through the content, finds image_prompt, generates images,
    and saves them to the Image model.
    """
    print("🎨 Generating illustrations...")

    image_count = 0
    for item in book_data.get("content", []):
        if item["type"] == "image_prompt":
            prompt = item["data"]
            image_count += 1
            print(f"  - Generating a picture {image_count}: {prompt[:50]}...")

            image_models = ["gemini-2.5-flash-image"]

            for img_model in image_models:
                try:
                    print(f"    - Trying with {img_model}...")
                    resp_alt = client.models.generate_content(
                        model=img_model,
                        contents=[prompt]
                    )
                    if resp_alt.candidates and resp_alt.candidates[0].content.parts:
                        for part in resp_alt.candidates[0].content.parts:
                            if part.inline_data:
                                image_bytes = part.inline_data.data
                                image_name = f"gen_{book.id}_{image_count}.png"

                                # Create an Image object and save it
                                image_instance = Image(
                                    book=book,
                                    image_prompt=prompt
                                )
                                image_instance.illustration.save(image_name, ContentFile(image_bytes), save=True)

                                # Add the path to the saved file to book_data
                                item["image_path"] = image_instance.illustration.path
                                print(f"    ✅ Image saved to model: {image_instance.illustration.name}")
                                break  # Exit the loop over models, as the image was successfully generated
                except Exception as e:
                    print(f"    ❌ Error with {img_model}: {e}")

    return book_data


def create_pdf(book_data, output_filename="generated_book.pdf"):
    """
    Creates a PDF file based on the received data.
    """
    print(f"📚 Create a PDF: {output_filename}...")
    doc = SimpleDocTemplate(output_filename, pagesize=letter)
    styles = getSampleStyleSheet()

    # Font setup
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

    # Title page
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph(book_data.get("title", "Book"), styles['BookTitle']))
    story.append(Paragraph(book_data.get("author", ""), styles['BookAuthor']))
    story.append(PageBreak())

    # Main content
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
    print(f"✨ PDF is ready: {output_filename}")


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
            # 1. We get the structure
            book_data = get_book_content_with_markers(book.text)
            book_llm_instance = BookLlm.objects.create(
                book=book,
                text=json.dumps(book_data, ensure_ascii=False, indent=2)
            )
            print("Step 1 finished")

            if settings.USE_TEST_IMAGES:
                print("Step 2: Using test images")
                test_images_dir = 'test_images'
                image_paths = [os.path.join(test_images_dir, f) for f in os.listdir(test_images_dir) if
                               f.endswith(('.png', '.jpg', '.jpeg'))]
                print(f"Found {len(image_paths)} test images.")

                image_index = 0
                for item in book_data.get("content", []):
                    if item["type"] == "image_prompt":
                        if image_index < len(image_paths):
                            source_path = image_paths[image_index]
                            filename = os.path.basename(source_path)

                            # Create an Image instance, but don't save it to the DB yet
                            image_instance = Image(book=book, image_prompt=item["data"])

                            # Copy the file to media and save it in the ImageField
                            with open(source_path, 'rb') as f:
                                image_instance.illustration.save(filename, ContentFile(f.read()), save=True)

                            item["image_path"] = image_instance.illustration.path
                            print(f"    ✅ Test image saved to model: {image_instance.illustration.name}")

                            image_index = (image_index + 1) % len(image_paths)  # Use images cyclically
                book_data_with_images = book_data
                book_llm_instance.text = json.dumps(book_data_with_images, ensure_ascii=False, indent=2)
                book_llm_instance.save()
                print("Step 2 finished")
            else:
                print("Step 2: Generating and saving images")
                # 2. Generate and save images
                book_data_with_images = generate_images(book, book_data)
                # Update the BookLlm record with image paths
                # book_llm_instance = BookLlm.objects.get(book=book)
                book_llm_instance.text = json.dumps(book_data_with_images, ensure_ascii=False, indent=2)
                book_llm_instance.save()
                print("Step 2 finished")

            print("Step 3: Creating PDF")
            # 3. Create PDF
            pdf_filename = f"generated_book_{book.id}.pdf"
            # Create a temporary directory if it doesn't exist
            temp_dir = os.path.join(settings.BASE_DIR, 'tmp')
            os.makedirs(temp_dir, exist_ok=True)
            temp_pdf_path = os.path.join(temp_dir, pdf_filename)

            create_pdf(book_data_with_images, temp_pdf_path)
            print("Step 3 finished")

            print("Step 4: Saving PDF to model")
            if os.path.exists(temp_pdf_path):
                with open(temp_pdf_path, 'rb') as f:
                    book_file = BookFile(book=book)
                    book_file.file.save(pdf_filename, f)
                    book_file.save()
                print("Step 4 finished")

                print("Step 5: Returning PDF from media")
                response = FileResponse(book_file.file, as_attachment=True, filename=pdf_filename)

                # 6. Remove the temporary file
                os.remove(temp_pdf_path)
                print("Step 6: Temporary PDF file removed")

                return response
            else:
                print("Error: PDF file not found.")
                return Response({"error": "PDF file not found."}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            print(f"An error occurred: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
