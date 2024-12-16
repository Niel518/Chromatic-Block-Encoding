import numpy as np
from PIL import Image, ImageDraw
import os
import math
import argparse
import sys

class ByteBlockEncoder:
    def __init__(self):
        self.DPI = 2550
        self.PAGE_WIDTH = int(210 * self.DPI / 25.4)
        self.PAGE_HEIGHT = int(297 * self.DPI / 25.4)
        self.MARGIN = 125
        
        # Fixed dimensions for all blocks
        self.BLOCK_WIDTH = 300
        self.BLOCK_HEIGHT = 300
        self.INNER_SCALE = math.sqrt(0.5)  # For inner rectangle (half area)
        
    def rgb_from_bytes(self, bytes_data, offset):
        """Convert 3 bytes to RGB color"""
        return (bytes_data[offset], bytes_data[offset + 1], bytes_data[offset + 2])
        
    def draw_block(self, draw, x, y, bytes_data):
        """Draw a single 15-byte block"""
        width = self.BLOCK_WIDTH
        height = self.BLOCK_HEIGHT
        
        # Calculate inner rectangle dimensions
        inner_width = int(width * self.INNER_SCALE)
        inner_height = int(height * self.INNER_SCALE)
        inner_x = x + (width - inner_width) // 2
        inner_y = y + (height - inner_height) // 2
        
        # Draw outer rectangle
        draw.rectangle([x, y, x + width, y + height], outline='black')
        
        # Draw trapezoids with colors from bytes (3 bytes per trapezoid)
        # Top trapezoid
        draw.polygon([
            (x, y),
            (x + width, y),
            (inner_x + inner_width, inner_y),
            (inner_x, inner_y)
        ], fill=self.rgb_from_bytes(bytes_data, 0))
        
        # Bottom trapezoid
        draw.polygon([
            (x, y + height),
            (x + width, y + height),
            (inner_x + inner_width, inner_y + inner_height),
            (inner_x, inner_y + inner_height)
        ], fill=self.rgb_from_bytes(bytes_data, 3))
        
        # Right trapezoid
        draw.polygon([
            (x + width, y),
            (x + width, y + height),
            (inner_x + inner_width, inner_y + inner_height),
            (inner_x + inner_width, inner_y)
        ], fill=self.rgb_from_bytes(bytes_data, 6))
        
        # Left trapezoid
        draw.polygon([
            (x, y),
            (x, y + height),
            (inner_x, inner_y + inner_height),
            (inner_x, inner_y)
        ], fill=self.rgb_from_bytes(bytes_data, 9))
        
        # Inner rectangle
        draw.rectangle(
            [inner_x, inner_y, inner_x + inner_width, inner_y + inner_height],
            fill=self.rgb_from_bytes(bytes_data, 12)
        )
        
        return width, height
        
    def create_header_block(self, filename, filesize, num_blocks):
        """Create 15-byte header block"""
        header = bytearray(15)
        
        # First 5 bytes: start of filename
        name = os.path.splitext(filename)[0][:5].encode()
        header[:len(name)] = name
        
        # Next 4 bytes: extension
        ext = os.path.splitext(filename)[1][1:].encode()[:4]
        header[5:5+len(ext)] = ext
        
        # 3 bytes for filesize
        header[9] = (filesize >> 16) & 0xFF
        header[10] = (filesize >> 8) & 0xFF
        header[11] = filesize & 0xFF
        
        # 3 bytes for number of blocks
        header[12] = (num_blocks >> 16) & 0xFF
        header[13] = (num_blocks >> 8) & 0xFF
        header[14] = num_blocks & 0xFF
        
        return header
        
    def create_footer_block(self, filename, data):
        """Create 15-byte footer block"""
        footer = bytearray(15)
        
        # Last 5 bytes of filename
        name = os.path.splitext(filename)[0][-5:].encode()
        footer[:len(name)] = name
        
        # Extension (4 bytes)
        ext = os.path.splitext(filename)[1][1:].encode()[:4]
        footer[5:5+len(ext)] = ext
        
        # Checksum (6 bytes)
        checksum = sum(data) & 0xFFFFFFFFFFFF
        for i in range(6):
            footer[9+i] = (checksum >> (40 - i*8)) & 0xFF
            
        return footer

    def encode_file(self, input_file, output_path):
        """Encode a file into the block format"""
        with open(input_file, 'rb') as f:
            data = f.read()
        
        # Calculate number of blocks needed (15 bytes per block)
        num_blocks = (len(data) + 14) // 15
        
        # Create header and footer
        header_block = self.create_header_block(os.path.basename(input_file), len(data), num_blocks)
        footer_block = self.create_footer_block(os.path.basename(input_file), data)
        
        # Create image
        img = Image.new('RGB', (self.PAGE_WIDTH, self.PAGE_HEIGHT), 'white')
        draw = ImageDraw.Draw(img)
        
        # Calculate grid layout
        blocks_per_row = (self.PAGE_WIDTH - 2 * self.MARGIN) // (self.BLOCK_WIDTH + self.MARGIN)
        
        # Process blocks
        x, y = self.MARGIN, self.MARGIN
        block_count = 0
        
        # Draw header
        self.draw_block(draw, x, y, header_block)
        x += self.BLOCK_WIDTH + self.MARGIN
        block_count += 1
        
        # Draw data blocks
        for i in range(0, len(data), 15):
            if x + self.BLOCK_WIDTH + self.MARGIN > self.PAGE_WIDTH:
                x = self.MARGIN
                y += self.BLOCK_HEIGHT + self.MARGIN
                
            if y + self.BLOCK_HEIGHT + self.MARGIN > self.PAGE_HEIGHT:
                raise ValueError("File too large to fit on single page")
                
            block = bytearray(15)
            block[:min(15, len(data)-i)] = data[i:i+15]
            self.draw_block(draw, x, y, block)
            
            x += self.BLOCK_WIDTH + self.MARGIN
            block_count += 1
            
        # Draw footer
        if x + self.BLOCK_WIDTH + self.MARGIN > self.PAGE_WIDTH:
            x = self.MARGIN
            y += self.BLOCK_HEIGHT + self.MARGIN
            
        self.draw_block(draw, x, y, footer_block)
        
        # Save the image
        output_file = output_path
        if os.path.isdir(output_path):
            base_name = os.path.splitext(os.path.basename(input_file))[0]
            output_file = os.path.join(output_path, f"{base_name}_encoded.png")
        elif not output_file.lower().endswith('.png'):
            output_file += '.png'
            
        img.save(output_file, 'PNG', dpi=(self.DPI, self.DPI))
        return output_file

def main():
    parser = argparse.ArgumentParser(description='Encode a file into a visual 15-byte block format')
    parser.add_argument('input_file', help='Input file to encode')
    parser.add_argument('output_path', help='Output PNG file or directory')
    
    args = parser.parse_args()
    
    try:
        encoder = ByteBlockEncoder()
        output_file = encoder.encode_file(args.input_file, args.output_path)
        print(f"File encoded successfully: {output_file}")
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()