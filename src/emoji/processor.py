"""Image processing and cropping utilities."""

import os
from PIL import Image
from typing import List, Tuple

from src.config.logger import get_logger
from src.config import settings

logger = get_logger()


class ImageProcessor:
    """Handles image cropping and emoji preparation."""

    def __init__(self):
        """
        Initialize image processor.
        """
        logger.info(f"ImageProcessor initialized")

    def crop_to_grid(
        self,
        input_path: str,
        output_folder: str,
        grid_size: Tuple[int, int],
        padding: int
    ) -> List[str]:
        """
        Crop image into NxM grid with padding.
        Args:
            input_path: Path to input image
            output_folder: Folder to save cropped images
            grid_size: Tuple of (columns, rows)
            padding: Padding value (1-5), each unit adds 3% transparent padding on each side
        Returns:
            List of paths to cropped images
        """
        logger.info(f"Starting crop_to_grid: input={input_path}, grid_size={grid_size}, padding={padding}")

        os.makedirs(output_folder, exist_ok=True)
        logger.debug(f"Created output folder: {output_folder}")

        logger.info(f"Opening image: {input_path}")
        img = Image.open(input_path)
        has_transparency = img.mode in ("RGBA", "LA", "P")
        if has_transparency and img.mode == "P":
            img = img.convert("RGBA")
            logger.debug(f"Converted palette image to RGBA to preserve transparency")
        elif img.mode != "RGBA":
            logger.debug(f"Converting image from {img.mode} to RGBA")
            img = img.convert("RGBA")

        original_width, original_height = img.size
        logger.info(f"Original image size: {original_width}x{original_height}")

        # Шаг 1: Добавляем прозрачный padding со всех сторон
        padding_percent = padding * 3
        padding_width = int(original_width * padding_percent / 100)
        padding_height = int(original_height * padding_percent / 100)

        new_width = original_width + 2 * padding_width
        new_height = original_height + 2 * padding_height

        logger.debug(f"Adding {padding_percent}% padding ({padding_width}px horizontal, {padding_height}px vertical)")
        logger.debug(f"Image with padding: {new_width}x{new_height}")

        padded_img = Image.new("RGBA", (new_width, new_height), (0, 0, 0, 0))
        padded_img.paste(img, (padding_width, padding_height))
        img.close()

        # Шаг 2: Resize до N*100 x M*100
        cols, rows = grid_size
        target_width = cols * 100
        target_height = rows * 100

        logger.info(f"Resizing to {target_width}x{target_height} (grid: {cols}x{rows})")
        resized_img = padded_img.resize(
            (target_width, target_height),
            Image.Resampling.LANCZOS
        )
        padded_img.close()

        # Шаг 3: Нарезаем на квадраты 100x100
        logger.info(f"Cutting into {cols * rows} tiles of 100x100px")
        cropped_files = []
        for row in range(rows):
            for col in range(cols):
                left = col * 100
                top = row * 100
                right = left + 100
                bottom = top + 100

                tile = resized_img.crop((left, top, right, bottom))

                output_filename = f"emoji_{row}_{col}.png"
                output_path = os.path.join(output_folder, output_filename)
                tile.save(output_path, "PNG", optimize=True)
                cropped_files.append(output_path)

        resized_img.close()
        logger.info(f"Successfully created {len(cropped_files)} emoji files")

        return cropped_files

    def suggest_grid_sizes(self, width: int, height: int) -> List[Tuple[int, int]]:
        """
        Suggest grid sizes based on image dimensions and 100px emoji size.
        Args:
            width: Image width
            height: Image height
        Returns:
            List of suggested grid sizes
        """
        import math

        logger.info(f"Calculating grid suggestions for {width}x{height}")

        max_cols = round(width / 100)
        max_rows = round(height / 100)

        # scale maximum cells
        scale = math.sqrt(settings.MAX_CELLS / (max_cols * max_rows))
        max_cols = int(max_cols * scale)
        max_rows = int(max_rows * scale)
        logger.info(f"Scaled to {max_cols}x{max_rows} = {max_cols * max_rows} cells")

        # scale max width
        if max_cols > settings.MAX_COLS:
            logger.info(f"max cols {max_cols} > {settings.MAX_COLS}. scale them to {settings.MAX_COLS}")
            scale = settings.MAX_COLS / (max_cols)
            max_cols = int(max_cols * scale)
            max_rows = int(max_rows * scale)
            logger.info(f"Scaled to {max_cols}")

        if max_cols < 2 or max_rows < 2:
            logger.warning(f"Image too small for minimum 2x2 grid with 100px emojis")
            return []

        logger.debug(f"Maximum grid: {max_cols}x{max_rows}")

        base_aspect = max_cols / max_rows
        logger.debug(f"Base aspect ratio: {base_aspect:.2f}")

        max_cells = max_cols * max_rows

        percentages = settings.SELECT_PERCENTAGES

        grid_sizes = []
        for pct in percentages:
            target_cells = int(max_cells * pct)

            cols = max(2, int(math.sqrt(target_cells * base_aspect)))
            rows = max(2, int(math.sqrt(target_cells / base_aspect)))

            while cols * rows > target_cells and (cols > 2 or rows > 2):
                if cols >= rows and cols > 2:
                    cols -= 1
                elif rows > 2:
                    rows -= 1
                else:
                    break

            if cols < 2 or rows < 2:
                logger.debug(f"Target {int(pct*100)}%: {cols}x{rows} is too small, skipping")
                continue

            current_aspect = cols / rows
            aspect_diff_ratio = abs(current_aspect - base_aspect) / base_aspect
            logger.debug(f"Target {int(pct*100)}%: {cols}x{rows} ({cols*rows} cells), aspect: {current_aspect:.2f}, diff: {aspect_diff_ratio:.1%}")

            if aspect_diff_ratio > settings.MIN_ASPECT_RATIO:
                logger.info(f"Aspect ratio deviation {aspect_diff_ratio:.1%} exceeds 30%, stopping at {len(grid_sizes)} sizes")
                break

            grid_sizes.append((cols, rows))

        seen = set()
        unique_sizes = []
        for size in grid_sizes:
            if size not in seen:
                seen.add(size)
                unique_sizes.append(size)

        logger.info(f"Suggested grid sizes: {unique_sizes}")
        return unique_sizes

    def get_image_dimensions(self, path: str) -> Tuple[int, int]:
        """
        Get image dimensions.

        Args:
            path: Path to image

        Returns:
            Tuple of (width, height)
        """
        logger.debug(f"Getting dimensions for: {path}")
        with Image.open(path) as img:
            dimensions = img.size
            logger.info(f"Image dimensions: {dimensions[0]}x{dimensions[1]}")
            return dimensions
