import os
import pickle
from functools import lru_cache
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from reader3 import Book, BookMetadata, ChapterContent, TOCEntry

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Where are the book folders located?
BOOKS_DIR = "."


def generate_slug_from_id(folder_name: str) -> str:
    """为旧书籍（无 slug 字段）生成 slug"""
    name = folder_name.replace("_data", "")
    return name.lower().replace(" ", "-").replace("_", "-")


def find_book_by_slug(slug: str) -> Optional[tuple[str, Book]]:
    """通过 slug 查找书籍，返回 (folder_name, book) 或 None"""
    if os.path.exists(BOOKS_DIR):
        for item in os.listdir(BOOKS_DIR):
            if item.endswith("_data") and os.path.isdir(os.path.join(BOOKS_DIR, item)):
                book = load_book_cached(item)
                if book and book.slug == slug:
                    return (item, book)
    return None


@lru_cache(maxsize=10)
def load_book_cached(folder_name: str) -> Optional[Book]:
    """
    Loads the book from the pickle file.
    Cached so we don't re-read the disk on every click.
    """
    file_path = os.path.join(BOOKS_DIR, folder_name, "book.pkl")
    if not os.path.exists(file_path):
        return None

    try:
        with open(file_path, "rb") as f:
            book = pickle.load(f)

        # 兼容旧书籍：如果没有 slug，动态生成
        if not book.slug:
            book.slug = generate_slug_from_id(folder_name)

        return book
    except Exception as e:
        print(f"Error loading book {folder_name}: {e}")
        return None

@app.get("/", response_class=HTMLResponse)
async def library_view(request: Request):
    """Lists all available processed books."""
    books = []

    # Scan directory for folders ending in '_data' that have a book.pkl
    if os.path.exists(BOOKS_DIR):
        for item in os.listdir(BOOKS_DIR):
            if item.endswith("_data") and os.path.isdir(os.path.join(BOOKS_DIR, item)):
                # Try to load it to get the title
                book = load_book_cached(item)
                if book:
                    books.append({
                        "slug": book.slug,
                        "title": book.metadata.title,
                        "author": ", ".join(book.metadata.authors),
                        "chapters": len(book.spine)
                    })

    return templates.TemplateResponse("library.html", {"request": request, "books": books})

@app.get("/read/{book_slug}", response_class=HTMLResponse)
async def redirect_to_first_chapter(
    book_slug: str,
    noindex: bool = Query(False)
):
    """Helper to just go to chapter 0."""
    result = find_book_by_slug(book_slug)
    if not result:
        raise HTTPException(status_code=404, detail="Book not found")
    folder_name, book = result
    return await read_chapter(
        request=None, book_slug=book_slug, folder_name=folder_name,
        chapter_index=0, noindex=noindex
    )

@app.get("/read/{book_slug}/{chapter_index}", response_class=HTMLResponse)
async def read_chapter(
    request: Request,
    book_slug: str,
    chapter_index: int,
    noindex: bool = Query(False, description="Hide sidebar navigation"),
    folder_name: str = None
):
    """The main reader interface."""
    if folder_name is None:
        result = find_book_by_slug(book_slug)
        if not result:
            raise HTTPException(status_code=404, detail="Book not found")
        folder_name, book = result
    else:
        book = load_book_cached(folder_name)

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    if chapter_index < 0 or chapter_index >= len(book.spine):
        raise HTTPException(status_code=404, detail="Chapter not found")

    current_chapter = book.spine[chapter_index]

    # Calculate Prev/Next links
    prev_idx = chapter_index - 1 if chapter_index > 0 else None
    next_idx = chapter_index + 1 if chapter_index < len(book.spine) - 1 else None

    return templates.TemplateResponse("reader.html", {
        "request": request,
        "book": book,
        "current_chapter": current_chapter,
        "chapter_index": chapter_index,
        "book_slug": book_slug,
        "prev_idx": prev_idx,
        "next_idx": next_idx,
        "noindex": noindex
    })

@app.get("/read/{book_slug}/images/{image_name}")
async def serve_image(book_slug: str, image_name: str):
    """
    Serves images specifically for a book.
    The HTML contains <img src="images/pic.jpg">.
    The browser resolves this to /read/{book_slug}/images/pic.jpg.
    """
    result = find_book_by_slug(book_slug)
    if not result:
        raise HTTPException(status_code=404, detail="Book not found")
    folder_name, _ = result

    safe_image_name = os.path.basename(image_name)
    img_path = os.path.join(BOOKS_DIR, folder_name, "images", safe_image_name)

    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(img_path)

if __name__ == "__main__":
    import uvicorn
    print("Starting server at http://127.0.0.1:8123")
    uvicorn.run(app, host="127.0.0.1", port=8123)
