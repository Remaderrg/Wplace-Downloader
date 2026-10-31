A Python script for downloading and stitching large rectangular areas from WPlace tile-based image service.

## How it works

The script works by analyzing tile URLs from the WPlace service. When you open the browser's developer tools (F12) and monitor network requests, you can see that images are loaded as individual tiles with coordinates in the URL format: `https://backend.wplace.live/files/s0/tiles/{x}/{y}.png`

The script allows you to:
1. Download multiple tiles within a specified rectangular area
2. Automatically stitch them together into a single large image

## Gallery

### Buenos Aires
![Buenos Aires](buenosD.png)

### Hong Kong
![Hong Kong](hongkonkD.png)

### Kyiv
![Kyiv](kyivD.png)

### Moscow
![Moscow](moscowD.png)

### Pyongyang
![Pyongyang](pyongyangD.png)

### Seoul
![Seoul](seoulD.png)

### Tokyo
![Tokyo](tokyoD.png)

## Prerequisites

Install the required dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the script:
```bash
python pixelmap.py
```

2. Follow the prompts:
   - **Output filename**: Enter the desired filename
   - **Coordinate x1**: Left boundary of the rectangle
   - **Coordinate y1**: Top boundary of the rectangle  
   - **Coordinate x2**: Right boundary of the rectangle
   - **Coordinate y2**: Bottom boundary of the rectangle

## How to find coordinates

1. Open your browser and navigate to the WPlace service
2. Open Developer Tools (F12)
3. Go to the Network tab
4. Zoom and pan to the area you want to capture
5. Look for image requests in the format `tiles/{x}/{y}.png`
6. Note the x,y coordinates of the tiles in your desired area
7. Use the minimum and maximum coordinates as your rectangle boundaries

## Example

If you want to download a 3x3 tile area starting from tile (1020, 677):
- x1: 1020, y1: 677
- x2: 1022, y2: 679

This will download 9 tiles and stitch them into one image.

## Output

- Downloaded tiles are stored in the `tiles_tmp/` directory
- The final stitched image is saved with your specified filename
- Temporary tiles can be deleted after successful stitching
