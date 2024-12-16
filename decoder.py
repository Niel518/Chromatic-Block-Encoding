import numpy as np
from PIL import Image, ImageFile
import os
import argparse
import sys

# Disable decompression bomb check and truncated image warnings
Image.MAX_IMAGE_PIXELS = None
ImageFile.LOAD_TRUNCATED_IMAGES = True

class ByteBlockDecoder:
    def __init__(self):
        self.DPI = 2550
        self.PAGE_WIDTH = int(210 * self.DPI / 25.4)
        self.PAGE_HEIGHT = int(297 * self.DPI / 25.4)
        self.MARGIN = 125
        self.BLOCK_WIDTH = 300
        self.BLOCK_HEIGHT = 300
        self.INNER_SCALE = 0.7071067811865476  # sqrt(0.5)

    def get_average_color(self, img_array, region):
        """Get average color of a region, avoiding edges"""
        x1, y1, x2, y2 = region
        # Sample from center area of region to avoid edge artifacts
        margin = 5
        sample_area = img_array[y1+margin:y2-margin, x1+margin:x2-margin]
        if sample_area.size == 0:
            return (0, 0, 0)
        return tuple(np.mean(sample_area, axis=(0, 1)).astype(int))

    def extract_colors(self, img_array, x, y):
        """Extract colors from the five sections of a block using region averaging"""
        width = self.BLOCK_WIDTH
        height = self.BLOCK_HEIGHT
        
        # Calculate inner rectangle dimensions
        inner_width = int(width * self.INNER_SCALE)
        inner_height = int(height * self.INNER_SCALE)
        inner_x = x + (width - inner_width) // 2
        inner_y = y + (height - inner_height) // 2

        # Define regions for color sampling
        regions = [
            # Top trapezoid: middle section
            (x + width//4, y, x + 3*width//4, inner_y),
            # Bottom trapezoid: middle section
            (x + width//4, inner_y + inner_height, x + 3*width//4, y + height),
            # Right trapezoid: middle section
            (inner_x + inner_width, y + height//4, x + width, y + 3*height//4),
            # Left trapezoid: middle section
            (x, y + height//4, inner_x, y + 3*height//4),
            # Inner rectangle: center area
            (inner_x + inner_width//4, inner_y + inner_height//4, 
             inner_x + 3*inner_width//4, inner_y + 3*inner_height//4)
        ]

        return [self.get_average_color(img_array, region) for region in regions]

    def colors_to_bytes(self, colors):
        """Convert RGB colors to bytes"""
        bytes_data = bytearray()
        for color in colors:
            bytes_data.extend(color)
        return bytes_data

    def parse_header(self, header_bytes):
        """Parse 15-byte header block"""
        try:
            # First 5 bytes: filename start
            filename = bytes(header_bytes[:5]).decode('utf-8', errors='ignore').rstrip('\x00')
            
            # Next 4 bytes: extension
            extension = bytes(header_bytes[5:9]).decode('utf-8', errors='ignore').rstrip('\x00')
            
            # 3 bytes for filesize
            filesize = (header_bytes[9] << 16) | (header_bytes[10] << 8) | header_bytes[11]
            
            # 3 bytes for number of blocks
            num_blocks = (header_bytes[12] << 16) | (header_bytes[13] << 8) | header_bytes[14]
            
            print(f"Debug - Raw header bytes: {[hex(b) for b in header_bytes]}")
            print(f"Debug - Filename bytes: {[hex(b) for b in header_bytes[:5]]}")
            print(f"Debug - Extension bytes: {[hex(b) for b in header_bytes[5:9]]}")
            
            return filename, extension, filesize, num_blocks
        except Exception as e:
            print(f"Header parsing error: {str(e)}")
            raise

    def verify_footer(self, footer_bytes, data, filename, extension):
        """Verify 15-byte footer block"""
        try:
            # Last 5 bytes of filename
            stored_name = bytes(footer_bytes[:5]).decode('utf-8', errors='ignore').rstrip('\x00')
            print(f"Debug - Footer name: {stored_name}")
            print(f"Debug - Expected name end: {filename[-5:] if len(filename) >= 5 else filename}")
            
            # Extension
            stored_ext = bytes(footer_bytes[5:9]).decode('utf-8', errors='ignore').rstrip('\x00')
            print(f"Debug - Footer extension: {stored_ext}")
            print(f"Debug - Expected extension: {extension}")
            
            # Checksum (6 bytes)
            stored_checksum = int.from_bytes(footer_bytes[9:15], 'big')
            calculated_checksum = sum(data) & 0xFFFFFFFFFFFF
            print(f"Debug - Stored checksum: {stored_checksum}")
            print(f"Debug - Calculated checksum: {calculated_checksum}")
            
            return stored_checksum == calculated_checksum
            
        except Exception as e:
            print(f"Footer verification error: {str(e)}")
            return False

    def decode_file(self, input_file, output_dir):
        """Decode an encoded PNG file"""
        image = Image.open(input_file)
        img_array = np.array(image)
        
        print(f"Image dimensions: {img_array.shape}")
        print(f"Image dtype: {img_array.dtype}")
        
        blocks_per_row = (self.PAGE_WIDTH - 2 * self.MARGIN) // (self.BLOCK_WIDTH + self.MARGIN)
        
        # Extract header block
        x, y = self.MARGIN, self.MARGIN
        header_colors = self.extract_colors(img_array, x, y)
        print("Debug - Header colors:", header_colors)
        header_bytes = self.colors_to_bytes(header_colors)
        
        filename, extension, filesize, num_blocks = self.parse_header(header_bytes)
        print(f"Decoding: {filename}.{extension}")
        print(f"Expected size: {filesize} bytes")
        print(f"Expected blocks: {num_blocks}")
        
        # Extract data blocks
        data = bytearray()
        block_count = 1  # Already processed header
        x += self.BLOCK_WIDTH + self.MARGIN
        
        while block_count < num_blocks + 1:  # +1 for header
            if x + self.BLOCK_WIDTH + self.MARGIN > self.PAGE_WIDTH:
                x = self.MARGIN
                y += self.BLOCK_HEIGHT + self.MARGIN
                
            colors = self.extract_colors(img_array, x, y)
            block_bytes = self.colors_to_bytes(colors)
            data.extend(block_bytes)
            
            x += self.BLOCK_WIDTH + self.MARGIN
            block_count += 1
            
            if block_count % 100 == 0:
                print(f"Processed {block_count} blocks...")
        
        # Extract and verify footer
        if x + self.BLOCK_WIDTH + self.MARGIN > self.PAGE_WIDTH:
            x = self.MARGIN
            y += self.BLOCK_HEIGHT + self.MARGIN
            
        footer_colors = self.extract_colors(img_array, x, y)
        footer_bytes = self.colors_to_bytes(footer_colors)
        
        if not self.verify_footer(footer_bytes, data[:filesize], filename, extension):
            raise ValueError("Footer verification failed - file may be corrupted")
            
        # Trim to actual file size
        data = data[:filesize]
        
        # Save decoded file
        output_file = os.path.join(output_dir, f"{filename}.{extension}")
        with open(output_file, 'wb') as f:
            f.write(data)
            
        print(f"Successfully decoded file: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Decode a visual byte block format back to original file')
    parser.add_argument('input_file', help='Input PNG file to decode')
    parser.add_argument('output_dir', help='Output directory for decoded file')
    
    args = parser.parse_args()
    
    try:
        if not os.path.exists(args.output_dir):
            os.makedirs(args.output_dir)
            
        decoder = ByteBlockDecoder()
        decoder.decode_file(args.input_file, args.output_dir)
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()