import os
import time
from PIL import Image
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import base64

url = "https://backend.wplace.live/files/s0/tiles/"

Image.MAX_IMAGE_PIXELS = None
# Максимальное количество плиток для объединения за раз (для экономии памяти)
MAX_TILES_PER_CHUNK = 100

def get_inclusive_range(a, b):
    start = min(a, b)
    end = max(a, b)
    return range(start, end + 1)

def save_tile_from_browser(url, x, y, save_dir, page, max_retries=1):
    tile_url = f"{url}{x}/{y}.png"
    filename = os.path.join(save_dir, f"tile_{x}_{y}.png")
    if os.path.exists(filename):
        print(f"File already exists: {filename}, skipping download.")
        return True, False
    for attempt in range(1, max_retries + 1):
        page.goto(tile_url)
        js = '''() => {
            const img = document.querySelector('img') || document.querySelector('body > img') || document.querySelector('body > image');
            if (!img) return null;
            const canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth;
            canvas.height = img.naturalHeight;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            return canvas.toDataURL('image/png').split(',')[1];
        }'''
        b64 = page.evaluate(js)
        if b64:
            with open(filename, 'wb') as f:
                import base64
                f.write(base64.b64decode(b64))
            print(f"Saved: {filename}")
            return True, True
        else:
            print(f"Attempt {attempt}: failed to get image {tile_url} via JS!")
            if attempt < max_retries:
                time.sleep(0.1)  # small delay between attempts
    print(f"Failed to download {tile_url} after {max_retries} attempts!")
    
    # Создаем пустой PNG файл 1000x1000
    empty_image = Image.new('RGBA', (1000, 1000), (0, 0, 0, 0))
    empty_image.save(filename)
    print(f"Created empty image: {filename}")
    return True, False

def stitch_tiles_chunk(x_values, y_values, save_dir, chunk_name):
    """Объединяет плитки в один чанк (ограниченное количество)"""
    tile_w, tile_h = None, None
    
    for y in y_values:
        for x in x_values:
            filename = os.path.join(save_dir, f"tile_{x}_{y}.png")
            if os.path.exists(filename):
                with Image.open(filename) as img:
                    tile_w, tile_h = img.size
                    break
        if tile_w and tile_h:
            break
    
    if not tile_w or not tile_h:
        raise ValueError(f"Could not find any downloaded tiles in chunk {chunk_name}")
    
    result_img = Image.new('RGBA', (tile_w * len(x_values), tile_h * len(y_values)))
    
    for row_idx, y in enumerate(y_values):
        for col_idx, x in enumerate(x_values):
            filename = os.path.join(save_dir, f"tile_{x}_{y}.png")
            if os.path.exists(filename):
                with Image.open(filename) as img:
                    result_img.paste(img, (col_idx * tile_w, row_idx * tile_h))
    
    return result_img

def stitch_tiles(x1, y1, x2, y2, save_dir):
    """Основная функция объединения с разделением на чанки"""
    x_values = list(get_inclusive_range(x1, x2))
    y_values = list(get_inclusive_range(y1, y2))
    
    total_tiles = len(x_values) * len(y_values)
    print(f"Total tiles to process: {total_tiles}")
    
    if total_tiles <= MAX_TILES_PER_CHUNK:
        print("Processing all tiles in one chunk...")
        return stitch_tiles_chunk(x_values, y_values, save_dir, "main")
    
    print(f"Large image detected ({total_tiles} tiles). Processing in chunks...")
    
    # Определяем оптимальное разбиение на чанки
    # Для прямоугольных изображений лучше разбивать по большей стороне
    if len(x_values) > len(y_values):
        # Широкое изображение - разбиваем по X
        tiles_per_chunk = MAX_TILES_PER_CHUNK // len(y_values)
        if tiles_per_chunk < 1:
            tiles_per_chunk = 1
        
        x_chunks = []
        for i in range(0, len(x_values), tiles_per_chunk):
            end_idx = min(i + tiles_per_chunk, len(x_values))
            x_chunk = x_values[i:end_idx]
            x_chunks.append(x_chunk)
        
        print(f"Created {len(x_chunks)} X-chunks (wide image)")
        
        # Обрабатываем каждый чанк
        chunk_files = []
        for i, x_chunk in enumerate(x_chunks):
            chunk_name = f"chunk_{i+1}"
            print(f"Processing {chunk_name} with {len(x_chunk)} X coordinates...")
            
            try:
                chunk_img = stitch_tiles_chunk(x_chunk, y_values, save_dir, chunk_name)
                chunk_filename = os.path.join(save_dir, f"{chunk_name}.png")
                chunk_img.save(chunk_filename)
                chunk_files.append(chunk_filename)
                print(f"Saved {chunk_name}: {chunk_filename}")
                
                # Освобождаем память
                chunk_img.close()
                del chunk_img
                
            except Exception as e:
                print(f"Error processing {chunk_name}: {e}")
                continue
        
        # Объединяем чанки в финальное изображение
        if len(chunk_files) == 1:
            print("Only one chunk, returning it directly")
            return Image.open(chunk_files[0])
        
        print("Combining X-chunks into final image...")
        
        # Загружаем первый чанк для получения размеров
        with Image.open(chunk_files[0]) as first_chunk:
            chunk_width, chunk_height = first_chunk.size
        
        # Создаем финальное изображение
        final_width = chunk_width * len(x_chunks)
        final_height = chunk_height
        final_img = Image.new('RGBA', (final_width, final_height))
        
        # Объединяем чанки по горизонтали
        for i, chunk_file in enumerate(chunk_files):
            with Image.open(chunk_file) as chunk_img:
                final_img.paste(chunk_img, (i * chunk_width, 0))
        
        # Удаляем временные файлы чанков
        for chunk_file in chunk_files:
            try:
                os.remove(chunk_file)
                print(f"Removed temporary chunk: {chunk_file}")
            except Exception as e:
                print(f"Could not remove {chunk_file}: {e}")
        
        return final_img
        
    else:
        # Высокое изображение - разбиваем по Y
        tiles_per_chunk = MAX_TILES_PER_CHUNK // len(x_values)
        if tiles_per_chunk < 1:
            tiles_per_chunk = 1
        
        y_chunks = []
        for i in range(0, len(y_values), tiles_per_chunk):
            end_idx = min(i + tiles_per_chunk, len(y_values))
            y_chunk = y_values[i:end_idx]
            y_chunks.append(y_chunk)
        
        print(f"Created {len(y_chunks)} Y-chunks (tall image)")
        
        # Обрабатываем каждый чанк
        chunk_files = []
        for i, y_chunk in enumerate(y_chunks):
            chunk_name = f"chunk_{i+1}"
            print(f"Processing {chunk_name} with {len(y_chunk)} Y coordinates...")
            
            try:
                chunk_img = stitch_tiles_chunk(x_values, y_chunk, save_dir, chunk_name)
                chunk_filename = os.path.join(save_dir, f"{chunk_name}.png")
                chunk_img.save(chunk_filename)
                chunk_files.append(chunk_filename)
                print(f"Saved {chunk_name}: {chunk_filename}")
                
                # Освобождаем память
                chunk_img.close()
                del chunk_img
                
            except Exception as e:
                print(f"Error processing {chunk_name}: {e}")
                continue
        
        # Объединяем чанки в финальное изображение
        if len(chunk_files) == 1:
            print("Only one chunk, returning it directly")
            return Image.open(chunk_files[0])
        
        print("Combining Y-chunks into final image...")
        
        # Загружаем первый чанк для получения размеров
        with Image.open(chunk_files[0]) as first_chunk:
            chunk_width, chunk_height = first_chunk.size
        
        # Создаем финальное изображение
        final_width = chunk_width
        final_height = chunk_height * len(y_chunks)
        final_img = Image.new('RGBA', (final_width, final_height))
        
        # Объединяем чанки по вертикали
        for i, chunk_file in enumerate(chunk_files):
            with Image.open(chunk_file) as chunk_img:
                final_img.paste(chunk_img, (0, i * chunk_height))
        
        # Удаляем временные файлы чанков
        for chunk_file in chunk_files:
            try:
                os.remove(chunk_file)
                print(f"Removed temporary chunk: {chunk_file}")
            except Exception as e:
                print(f"Could not remove {chunk_file}: {e}")
        
        return final_img

def main():
    output_filename = input("Enter output filename: ")
    if not (output_filename.lower().endswith('.png') or output_filename.lower().endswith('.jpg') or output_filename.lower().endswith('.jpeg')):
        output_filename += '.png'
    x1 = int(input("Enter coordinate x1: "))
    y1 = int(input("Enter coordinate y1: "))
    x2 = int(input("Enter coordinate x2: "))
    y2 = int(input("Enter coordinate y2: "))
    print(f"Output file: {output_filename}")
    print(f"Rectangle points: ({x1}, {y1}) and ({x2}, {y2})")

    save_dir = "tiles_tmp"
    os.makedirs(save_dir, exist_ok=True)
    x_values = list(get_inclusive_range(x1, x2))
    y_values = list(get_inclusive_range(y1, y2))
    with sync_playwright() as p:
        def launch():
            b = p.chromium.launch(headless=False)
            page = b.new_page()
            try:
                page.set_default_navigation_timeout(10000)
                page.set_default_timeout(10000)
            except Exception:
                pass
            return b, page

        browser, page = launch()
        try:
            for y in y_values:
                for x in x_values:
                    restart_attempts = 0
                    while True:
                        try:
                            success, downloaded_now = save_tile_from_browser(url, x, y, save_dir, page)
                            if success and downloaded_now:
                                time.sleep(1)
                            break
                        except PlaywrightTimeoutError:
                            print("Page load timeout. Restarting browser and continuing...")
                            try:
                                browser.close()
                            except Exception:
                                pass
                            browser, page = launch()
                            restart_attempts += 1
                            if restart_attempts >= 1:
                                print(f"Skipping tile {x},{y} after 1 restarts.")
                                break
        finally:
            try:
                browser.close()
            except Exception:
                pass
    try:
        result_img = stitch_tiles(x1, y1, x2, y2, save_dir)
        result_img.save(output_filename)
        print(f"Image saved to {output_filename}")
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
