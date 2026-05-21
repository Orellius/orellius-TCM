Watermark Reference Images
==========================

Place cropped PNG images of source-channel watermarks here.

Directory structure:
  global/             — Watermarks common across all channels
  {channel_name}/     — Watermarks specific to a channel (e.g., @some_channel/)

How to create a reference image:
  1. Take a screenshot of a watermarked image from the source channel
  2. Crop tightly around the watermark/logo only
  3. Save as PNG (transparency supported)
  4. Place in the appropriate directory

Channel-specific directories are created automatically when you
upload references via the API or settings UI.

Notes:
  - Supported formats: PNG (recommended), JPG
  - Keep images small (the actual watermark size, not the full photo)
  - Template matching works best with clean, high-contrast logos
  - The detector tries multiple scales (50%-150%), so exact size matching isn't required
