---
title: This or That: a model that learns your taste in 50 taps
postit: This or That
label: a side project that got out of hand
description: How I built This or That, a game where a small model learns your taste in art from 50 picks and then predicts your next 20.
draft-note: Drafted by Claude from the research notes (taste/CONTEXT.md). Check the numbers and the tone, then delete this line.
---
**[Play it here →](https://this-or-that-six.vercel.app)** It takes two minutes and works best on a phone.

You see two artworks and tap the one you like more. After 50 picks, a small model has learned your taste. Then it plays 20 more rounds, and before each one it locks in a guess about which image you'll pick. At the end you see how often it was right, and how often a model of *everyone's* taste would have been right instead.

## Why I built it

I want generative models with taste. Not average taste: averaging thousands of opinions is exactly how you get images nobody dislikes and nobody loves. One person's taste.

To train a generator on someone's taste, you first need a critic that actually knows it. If the critic is wrong, the generator learns to fool the critic instead of pleasing the person. So step one was to build that critic and prove it works before training anything.

## Is personal taste even real?

It could have been noise: maybe everyone mostly agrees, and the rest is mood. I used LAPIS, a public dataset of 281,000 ratings of 11,723 artworks by 555 people, each rating about 500 images.

For every person I asked: once you know what the crowd thinks of an image, can you predict how this person deviates from the crowd, on images the model hasn't seen? Using only the dataset's metadata about each artwork (no image model yet) and a strict significance test, the answer was yes for **530 of 553 people**. Taste is consistent and personal.

## The critic

Each image goes through a frozen CLIP model. On top sits a model of the crowd's preference, plus a small correction per person. I tested it on 18 people, eight picked for unusual taste and ten at random. For all 18, their own critic predicted their choices better than the crowd model, and better than any of the other 17 people's critics.

## Making 50 taps enough

That critic needed hundreds of answers per person. Nobody taps 500 times on a website.

Two things fixed it. First, taste turned out to be low-dimensional: fit on all 555 people, eight axes explain it, things like *crowd-pleaser vs. against the grain*, *quiet minimalism vs. vivid painting*, *raw gestural marks vs. polished detail*. So a person is about eight numbers, and eight numbers can be learned from a few dozen answers.

Second, the app doesn't show random pairs. After a few warm-up rounds, it picks the pair it would learn the most from. With that, 25 answers are worth about 150 to 200 random ones.

## The test can't cheat

The 20 test rounds are fixed before the game shows them, and the guess is locked before you see the pair. Five are pairs the model is sure about, five are "contrarian" pairs where your model and the crowd model disagree, and ten are random.

In simulation on 58 people the model had never seen, it got 16.5 of 20 right on average, and beat the crowd model in 93% of games. My own result: **16 of 20, against 9 of 20 for the crowd model.** Apparently I'm against the grain, into stark black and white, raw gestural marks and baroque drama. Fair.

## What didn't work

- **Fine-tuning the image encoder** gained 0.2 points, then overfit. About 10,000 images is not enough.
- **Teaching an image generator my taste** (Stable Diffusion with reinforcement learning, using the critic as the reward) is parked. The generator learned to raise the CLIP-based reward, but a second, independent critic barely moved: textbook reward hacking. In a blind test I couldn't reliably prefer its images either.

The critic works. Turning it into a generator is the next hard part.

## How it's built

A static site plus one serverless function. Your eight numbers are fitted in your browser, in JavaScript, by the same maths as the Python research code. Sessions are stored anonymously, so I can check the model on real players.

Artworks come from the LAPIS dataset (Maerten et al., 2025), CC BY-NC 4.0.
