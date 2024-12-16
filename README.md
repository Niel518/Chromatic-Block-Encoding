# Chromatic Block Encoding

## Overview
A file encoding and decoding system that transforms binary data into a visually structured image representation. This encoder turns any file into a PNG image where data is embedded using geometric shapes and color-coded sections, and then the decoder turns it back to the original file.

## Key Features
- Encode any file into a visually intricate PNG image
- Preserves complete file metadata (filename, extension, size)
- Supports files of various sizes
- High-resolution encoding (2550 DPI)
- Simple command-line interface
- Built-in error checking with file checksum verification

## How It Works
Each 15-byte block is represented as a rectangle with:
- Trapezoids and inner rectangle colored to represent data
- Header and footer blocks for file metadata and verification

## Usage

### Encoding
```bash
python encoder.py "input_file_path" "output_directory"
