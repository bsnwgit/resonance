# Using Resonance

This is for anyone standing in front of the display. You do not need an
account and there is nothing to install — the screen is the whole interface.

## What you are looking at

A figure in the middle of the screen that moves while it listens and while it
speaks. It is not decoration: the shape is driven by what the microphone hears
and by what the assistant is saying, so you can tell at a glance whether the
system heard you, is thinking, or has started to answer. When nothing is
happening it idles quietly.

Below it is the transcript, and below that a single input row.

Between them is a dim line that reports what just happened — what it heard,
how long transcription took, or why nothing came of it. You can ignore it
entirely; it is there for the times when you press TALK, speak, and nothing
appears. Then it will say whether it heard nothing at all, heard you and
matched no assistant's name, or reached one that failed. Hiding the transcript
with **TEXT** hides this line too.

## The four controls

They sit along the bottom right. Each one is a toggle — press it and it stays
that way.

| Control | What it does |
|---|---|
| SPACE / AUTO | How it decides you have finished speaking |
| TALK | Opens the microphone |
| AUDIO | Mutes or unmutes its voice |
| TEXT | Shows or hides the transcript |

### SPACE and AUTO

**SPACE** is push-to-talk. Hold the space bar while you speak and release when
you are done. Nothing is sent until you release, so a cough or a colleague
talking behind you costs nothing.

**AUTO** is hands-free. It listens for you to stop and sends when you do. This
is the right mode for a screen on a wall that people walk up to; SPACE is the
right mode at a desk in a noisy room.

Click the control to switch between them.

### TALK

Opens the microphone. Nothing is transcribed until you press it, and the
button reports what state it is in — TALK, HOLD SPACE, or listening.

The browser will ask permission the first time. If it never asks, see
**When the microphone will not open** below.

### AUDIO

Mutes the spoken reply. The answer still arrives and still appears in the
transcript; it simply is not read out. Useful in a shared room.

### TEXT

Hides the transcript and gives the space to the figure. The conversation still
happens — this only affects what is on screen. Turn it off for a display that
is mostly being looked at rather than read.

**On some screens this button is not there.** A display mounted on a wall can be
set to voice only by whoever runs it, and then there is no transcript and no
typing on that screen at all — only the figure and your voice. The button is
taken away rather than left there refusing you, because a control that ignores
you is worse than one that was never offered. Everything else works exactly as
it does anywhere else.

## When the screen shrinks and dims

Leave a display alone for long enough and the figure gets smaller, dims, and
begins to drift slowly around the screen. Nothing is wrong: this is the
screensaver, and it is the same picture with the same settings, moved.

Screens that show the same bright shape in the same place for years end up
keeping a ghost of it permanently. Making it smaller, darker and slowly moving
is what prevents that. It is also simply what a screen in a hallway should be
doing in the middle of the night.

**Say the wake word or touch the screen and it comes straight back**, easing
back to the middle rather than snapping. The transcript and the buttons return
the moment you touch it. It will not start while it is thinking about an answer
or speaking one, and if nothing happens when you leave a screen alone, then
whoever runs it has not switched it on for that display.

## Typing instead of talking

The field along the bottom takes typed questions. Press Enter to send. Talking
and typing are the same conversation, so you can start with your voice and
finish with the keyboard.

## Wake and sleep words

An administrator may have set one or more wake words. If so, the display
ignores what it hears until it hears one of them — which is what makes it
usable in a room where people are talking to each other rather than to it.

**Each name reaches a different assistant.** Say one and everything after it
goes there: the question you asked, and the follow-up after that, without
having to say the name again. Say a *different* name mid-conversation and you
switch — one person at one screen changing what they are addressing. What was
said to the first one does not come with you, which is the point.

You may hear which one answered rather than read it: an administrator can
give each a different voice, and each can greet you in its own words.

Once woken it stays awake for a set period and then goes quiet on its own. You
can also end the conversation deliberately with the sleep word, if one is
configured — one word, whichever assistant you were talking to. Ask your
administrator which words are set.

**An assistant wired to a house behaves like any other.** Ask it to switch a
light on, it confirms, and it keeps listening — so a second command needs no
second wake word. If it asks you something back — *"which room?"* — just answer.
Either way the conversation ends the usual way: the sleep word, or the pause.

**Going to sleep clears the conversation.** This is deliberate — see below.

**Some names are not for every screen.** An administrator can restrict an
assistant — usually one that switches things on and off — to particular
displays. A screen that is not on that list stays silent when it hears that
name: it does not answer, and it does not hand what it heard to whatever it was
already talking to, because you were addressing a different device. Its status
line says so if you look. Speak to the display that owns the name, or ask your
administrator to add this one.

**A newly installed screen may be waiting to be approved.** It looks exactly
right and answers to nothing; the line above the box says so, and gives the id
an administrator needs. Approving it takes one click over in the panel, and the
screen picks it up on its own within a few seconds — nobody needs to touch it.

## Asking for access

On some installations, opening the page on your own laptop or phone gives you
the figure and a short form instead of the transcript and the input box. That
means this device has not been given access to anything yet.

Fill the form in — an administrator chose what it asks for — and press REQUEST
ACCESS. Nothing else is needed from you: leave the page open, or come back to
it later. When somebody decides, the screen tells you in a box you have to
dismiss, so you find out whether you were approved even if you had walked away.

**If you are turned down** you are shown the reason they wrote, and whether you
may ask again.

**Access can run out.** Where it does, the page comes back to the same screen
saying so — but with an ASK AGAIN button rather than the form, because what you
told them the first time is still on record. One press, and you wait for the
same decision.

**A refusal, and access itself, belong to the device you are using**, not to
you. Your laptop being turned down says nothing about your phone: that is a
separate device, and it asks separately.

## What it remembers

Two different things, and it is worth knowing which is which.

**The conversation** is held for as long as the session lasts, so you can say
"and what about the other one?" and be understood. It is discarded when the
display goes to sleep. Nothing about the conversation is written to disk.

**Your four control settings** are remembered in your own browser, so the
display comes back the way you left it. They stay until you clear your browser
data. They are yours alone — they do not change what anyone else sees, and
they are not sent to the server.

## When the microphone will not open

Browsers only allow microphone access on a secure origin. If you reached the
display over plain `http://`, the microphone is blocked by the browser and no
setting in Resonance can unblock it — the fault is in the address, not the
app.

Use the `https://` address instead. Everything else on the page works either
way; only the microphone is affected. If you do not know the secure address,
ask your administrator.

If you are on `https://` and it still does not work:

- Check the browser has not remembered a "block" decision for this site. In
  most browsers this is the padlock or shield in the address bar.
- Check no other application has the microphone open.
- On a shared machine, check the operating system's own microphone permission.

## If it mishears you

- Speak at a normal pace. Slowing down unnaturally makes transcription worse,
  not better.
- In SPACE mode, start speaking after you press, not as you press.
- If it consistently mishears one particular word, tell your administrator —
  there is an accuracy setting they can change.
- **Read the dim line above the input box.** It quotes what it actually heard,
  which is usually the whole answer: a name transcribed slightly wrong is
  refused by an assistant set to answer only to the exact word, and that line
  is the only place you can see it happen.

## Getting a better answer

The assistant is told to keep replies short, because they are read aloud and a
long spoken answer is hard to follow. If you want more, ask for it directly:
"explain that in more detail" works.

If it says something that looks like a formatting error — reading out asterisks
or hyphens — that is worth reporting. The reply should be plain prose.
