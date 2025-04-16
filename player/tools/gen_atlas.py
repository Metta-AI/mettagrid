import pixie
import os
import json

# Pack all of the images into a single atlas.
# We are using Skyline bin packing algorithm, its simple to implement, fast,
# and works well small number of images. No fancy packing required!
atlas_image = pixie.Image(2048, 2048)
images = {}
heights = [0] * atlas_image.width
margin = 6

# Create an 64x64 white image and put it first at 0,0.
# This image is used to draw solid colors.
white_image = pixie.Image(64, 64)
white_image.fill(pixie.Color(1, 1, 1, 1))
atlas_image.draw(white_image, pixie.translate(0, 0))
images["white.png"] = (0, 0, white_image.width, white_image.height)
for i in range(white_image.width + margin):
    heights[i] = white_image.height + margin

for file in os.listdir("data"):
    if file.endswith(".png"):
        img = pixie.read_image("data/" + file)

        # Find the lowest value in the heights array.
        min_height = atlas_image.height
        min_x = -1
        for i in range(len(heights)):
            if heights[i] < min_height:
                this_height = heights[i]
                this_x = i
                # Are all heights less then this image?
                for j in range(1, img.width):
                    if i + j + margin >= len(heights) or heights[i + j] > this_height:
                        break
                else:
                    print("found", file, this_x, this_height)
                    min_height = this_height
                    min_x = this_x

        if min_x == -1:
            quit("failed to find a place for: " + file)

        # Draw the image at the lowest value.
        atlas_image.draw(img, pixie.translate(min_x, min_height))
        images[file] = (min_x, min_height, img.width, img.height)

        # Update the heights array.
        for i in range(img.width + margin):
            heights[min_x + i] = min_height + img.height + margin

# Write the atlas image and the atlas json file.
with open("dist/atlas.json", "w") as f:
    json.dump(images, f)
atlas_image.write_file("dist/atlas.png")
