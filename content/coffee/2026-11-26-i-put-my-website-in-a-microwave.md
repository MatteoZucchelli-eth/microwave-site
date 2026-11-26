---
title: I put my website in a microwave
draft-note: Drafted by Claude from how the site was built. Rewrite it in your voice before publishing.
---
The homepage is a beige office microwave. The things on the turntable are the menu. It looks rendered because it is: every pixel comes out of Blender's Cycles path tracer, not a game engine.

## Why not WebGL

Real-time rendering is good, but a path tracer is better at the things that make a breakroom look like a breakroom: soft fluorescent light, a glass plate, the glow through a perforated door. So nothing on the homepage is rendered in your browser. It's all pre-rendered, then stacked on a canvas.

## Layers, not a video

A single video would mean re-rendering everything whenever a project changes. Instead the scene is split into layers:

- a background (the plate is a perfect disc, so one frame covers the whole rotation),
- one layer per object, rendered alone on its slot with a shadow catcher, 120 frames per turn,
- the door, swinging open in 24 frames.

Adding a project means rendering one object. The browser composites the layers every frame, back to front, using each object's depth.

## The part that didn't work

Compositing the closed door over the interior came out 40% too dark. The cavity is brighter than white, and in the real render the door mesh averages that light *before* tone mapping. 8-bit layers can't. So the closed state is one exact frame, and each object gets a second render as seen through the door's holes.

## The details

The timer, the post-it, and the clock are HTML, warped onto the render with a homography. The objects you can click are hit-tested per pixel, so you're clicking the pretzel, not its bounding box.

It's the most over-engineered menu I've ever made.
