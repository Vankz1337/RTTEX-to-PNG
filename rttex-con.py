
from pathlib import Path
from io import BytesIO
from zipfile import ZipFile
from PIL import Image, ImageDraw
from growtopia.rttex_converter import rttex_unpack
import json
import sys

ARCHIVE = Path(sys.argv[1] if len(sys.argv) > 1 else "player.zip")
OUTPUT = Path("player_assets")
SOURCE = OUTPUT / "extracted"
PNG_DIR = OUTPUT / "png"

SOURCE.mkdir(parents=True, exist_ok=True)
PNG_DIR.mkdir(parents=True, exist_ok=True)

if not ARCHIVE.exists():
    raise SystemExit(f"File tidak ditemukan: {ARCHIVE}")

# Ekstrak RTTEX dengan aman.
with ZipFile(ARCHIVE, "r") as archive:
    for info in archive.infolist():
        if info.is_dir():
            continue

        target = (SOURCE / info.filename).resolve()
        if not target.is_relative_to(SOURCE.resolve()):
            continue

        if info.filename.lower().endswith(".rttex"):
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(info))

records = []
errors = []

for rttex in SOURCE.rglob("*.rttex"):
    relative = rttex.relative_to(SOURCE).with_suffix(".png")
    output = PNG_DIR / relative
    output.parent.mkdir(parents=True, exist_ok=True)

    try:
        with rttex.open("rb") as stream:
            raw_data = stream.read()
            converted = rttex_unpack(raw_data)
            # Normalisasi hasil converter menjadi bytes.
            if isinstance(converted, (bytes, bytearray, memoryview)):
                png_data = bytes(converted)
            elif hasattr(converted, "getvalue"):
                png_data = converted.getvalue()
            elif hasattr(converted, "read"):
                converted.seek(0)
                png_data = converted.read()
            else:
                raise TypeError(
                    f"Tipe hasil converter tidak dikenal: {type(converted)}"
                )
        with Image.open(BytesIO(png_data)) as image:
            image.load()
            rgba = image.convert("RGBA")
            rgba.save(output, "PNG")

            alpha_min, alpha_max = rgba.getchannel("A").getextrema()

            records.append({
                "source": str(rttex.relative_to(SOURCE)),
                "png": str(output.relative_to(OUTPUT)),
                "width": rgba.width,
                "height": rgba.height,
                "mode": rgba.mode,
                "has_transparency": alpha_min < 255
            })

        print(f"[OK] {rttex.name}")

    except Exception as error:
        errors.append({
            "file": str(rttex.relative_to(SOURCE)),
            "error": str(error)
        })
        print(f"[ERROR] {rttex.name}: {error}")

# Simpan manifest.
manifest = {
    "archive": ARCHIVE.name,
    "total_rttex": len(records) + len(errors),
    "converted": len(records),
    "failed": len(errors),
    "textures": records,
    "errors": errors
}

(OUTPUT / "player_manifest.json").write_text(
    json.dumps(manifest, indent=2),
    encoding="utf-8"
)
if records:
    columns = 4
    cell_w, cell_h = 240, 190
    rows = (len(records) + columns - 1) // columns

    sheet = Image.new(
        "RGB",
        (columns * cell_w, rows * cell_h),
        (45, 45, 45)
    )
    draw = ImageDraw.Draw(sheet)

    for index, record in enumerate(records):
        image_path = OUTPUT / record["png"]
        image = Image.open(image_path).convert("RGBA")
        image.thumbnail((210, 140))

        x = (index % columns) * cell_w
        y = (index // columns) * cell_h

    
        preview = Image.new("RGBA", (220, 145), (100, 100, 100, 255))
        for cy in range(0, 145, 16):
            for cx in range(0, 220, 16):
                if (cx // 16 + cy // 16) % 2:
                    draw_color = (145, 145, 145, 255)
                else:
                    draw_color = (90, 90, 90, 255)
                ImageDraw.Draw(preview).rectangle(
                    (cx, cy, cx + 15, cy + 15),
                    fill=draw_color
                )

        px = (220 - image.width) // 2
        py = (145 - image.height) // 2
        preview.alpha_composite(image, (px, py))

        sheet.paste(preview.convert("RGB"), (x + 10, y + 5))
        draw.text(
            (x + 10, y + 155),
            Path(record["source"]).name[:32],
            fill="white"
        )
        draw.text(
            (x + 10, y + 171),
            f'{record["width"]} x {record["height"]}',
            fill="white"
        )

    sheet.save(OUTPUT / "contact_sheet.png")

if errors:
    (OUTPUT / "conversion_errors.txt").write_text(
        "\n".join(f'{e["file"]}: {e["error"]}' for e in errors),
        encoding="utf-8"
    )

print("\n=== SELESAI ===")
print("Berhasil:", len(records))
print("Gagal:", len(errors))
print("Hasil:", OUTPUT.resolve())
