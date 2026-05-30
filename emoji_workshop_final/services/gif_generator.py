"""GIF 表情包生成器"""

from PIL import Image, ImageDraw, ImageFont


class GifGenerator:
    @staticmethod
    def make_text_animated_gif(
        base_image_path: str,
        text: str,
        output_path: str,
        frames: int = 10,
        duration: int = 150,
    ) -> str:
        base = Image.open(base_image_path).convert("RGBA")
        width, height = base.size

        try:
            font = ImageFont.truetype("msyh.ttc", 36)
        except OSError:
            font = ImageFont.load_default()

        images = []
        for i in range(frames):
            frame = base.copy()
            draw = ImageDraw.Draw(frame)
            half = max(frames // 2, 1)
            if i < half:
                progress = i / half
                y_offset = height - 50 - int(progress * 30)
                alpha = int(255 * progress)
            else:
                y_offset = height - 80
                alpha = 255 if (i - half) % 2 == 0 else 120

            bbox = draw.textbbox((0, 0), text, font=font)
            text_w = bbox[2] - bbox[0]
            x = (width - text_w) // 2
            draw.text(
                (x, y_offset),
                text,
                font=font,
                fill=(255, 230, 0, alpha),
                stroke_width=2,
                stroke_fill=(0, 0, 0, alpha),
            )
            images.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))

        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0,
            optimize=True,
        )
        return output_path

    @staticmethod
    def make_multiframe_gif(image_paths: list[str], output_path: str, duration: int = 200) -> str:
        images = [
            Image.open(p).convert("RGBA").convert("P", palette=Image.Palette.ADAPTIVE)
            for p in image_paths
        ]
        images[0].save(
            output_path,
            save_all=True,
            append_images=images[1:],
            duration=duration,
            loop=0,
        )
        return output_path
