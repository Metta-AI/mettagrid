## AoE (Area of Effect) panel.

import
  silky, vmath,
  ../common

proc drawAoePanel*(panel: Panel, frameId: string, contentPos: Vec2, contentSize: Vec2) =
  ## Draw the AoE panel.
  frame(frameId, contentPos, contentSize):
    sk.at += vec2(8, 8)
    text("AoE overlay is shown on the map.")
