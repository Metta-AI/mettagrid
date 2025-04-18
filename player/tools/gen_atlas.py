import pixie
import os
import json

# Pack all of the images into a single atlas.
# We are using Skyline bin packing algorithm, its simple to implement, fast,
# and works well small number of images. No fancy packing required!
atlas_image = pixie.Image(2048, 2048)
images = {}
heights = [0] * atlas_image.width
padding = 8


def put_image(img, name, x=None, y=None):
    """
    Place an image in the atlas at the specified coordinates or find the best position.

    Args:
        img: The pixie Image to place in the atlas
        name: The name/key to use in the images dictionary
        x: Optional x coordinate to place the image at
        y: Optional y coordinate to place the image at

    Returns:
        Tuple of (x, y, width, height) indicating the image position
    """
    global heights, atlas_image, images

    # Create a new image with padding
    padded_img = pixie.Image(img.width + 2 * padding, img.height + 2 * padding)
    padded_img.fill(pixie.Color(0, 0, 0, 0))
    padded_img.draw(img, pixie.translate(padding, padding))
    # Duplicate the edges padding to the edges of the image.
    top_line = img.sub_image(0, 0, img.width, 1)
    bottom_line = img.sub_image(0, img.height - 1, img.width, 1)
    left_line = img.sub_image(0, 0, 1, img.height)
    right_line = img.sub_image(img.width - 1, 0, 1, img.height)

    for p in range(padding):
        h = padded_img.height - p - 1
        w = padded_img.width - p - 1
        padded_img.draw(top_line, pixie.translate(padding, p))
        padded_img.draw(bottom_line, pixie.translate(padding, h))
        padded_img.draw(left_line, pixie.translate(p, padding))
        padded_img.draw(right_line, pixie.translate(w, padding))

    # If coordinates are provided, use them
    if x is not None and y is not None:
        atlas_image.draw(padded_img, pixie.translate(x, y))
        images[name] = (x, y, padded_img.width, padded_img.height)

        # Update the heights array
        for i in range(img.width):
            if x + i < len(heights):
                heights[x + i] = y + img.height

        return images[name]

    # Find the lowest value in the heights array
    min_height = atlas_image.height
    min_x = -1
    for i in range(len(heights)):
        if heights[i] < min_height:
            this_height = heights[i]
            this_x = i

            # Check if there's enough space for the image
            for j in range(1, padded_img.width):
                if this_x + j >= len(heights) or heights[this_x + j] > this_height:
                    break
            else:
                print("found", name, this_x, this_height)
                min_height = this_height
                min_x = this_x

    if min_x == -1:
        quit("failed to find a place for: " + name)

    # Draw the image at the position
    atlas_image.draw(padded_img, pixie.translate(min_x, min_height))
    images[name] = (min_x + padding, min_height + padding, img.width, img.height)

    # Update the heights array
    for i in range(padded_img.width):
        if min_x + i < len(heights):
            heights[min_x + i] = min_height + padded_img.height

    return images[name]


# Create an 64x64 white image and put it first at 0,0.
# This image is used to draw solid colors.
white_image = pixie.Image(64, 64)
white_image.fill(pixie.Color(1, 1, 1, 1))
put_image(white_image, "white.png", 0, 0)

for file in os.listdir("data"):
    if file.endswith(".png"):
        img = pixie.read_image("data/" + file)
        put_image(img, file)

# Write the atlas image and the atlas json file.
with open("dist/atlas.json", "w") as f:
    json.dump(images, f)
atlas_image.write_file("dist/atlas.png")
