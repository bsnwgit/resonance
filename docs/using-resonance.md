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
appears. Then it will say whether it heard nothing at all, or reached an
assistant that failed. Speech that named no assistant is not reported: it was
not addressed to this screen, so the line stays empty and the button reads
ASLEEP. Hiding the transcript with **TEXT** hides this line too.

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

**On some screens this button is not there.** A display set up as a kiosk — on
a wall, a stand, a counter — is usually voice only, and then there is no
transcript and no typing on that screen at all
— only the figure and your voice. The button is taken away rather than left
there refusing you, because a control that ignores you is worse than one that
was never offered.

**A kiosk has no SPACE button either.** Holding the space bar is a way of
talking to it that assumes a keyboard, and a screen people walk up to does not
have one.
Those screens always listen, so you say the wake word instead — which is what
the line low on the screen is telling you.

**A kiosk usually fills the display when you touch it.** The browser's own bars
disappear and the figure takes the whole panel. If you need them back — to read
the address, or to reload — press Escape, and they stay for a minute before it
goes full screen again.

## What to say to it

A kiosk usually shows one dim line near the bottom: **say “kitchen”**, or
whatever it has been named — or whatever whoever set it up chose to write
there. That is the whole instruction. Say it, wait for the
figure to react, then ask your question.

The line is not there while you are talking to it — the answer is more use than
the instruction — and it comes back when the conversation ends. If the screen
has drifted into its screensaver, the line has drifted with it and is sitting
under the figure wherever that has got to.

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

## When it is thinking

Three dots appear where the answer will be, brightening one after another,
from the moment you ask until the reply arrives. They mean it is working.

Most answers come back in a moment. One that has to look something up in the
application the assistant is embedded in takes longer — the question goes out,
the answer comes back, and the assistant reads it before it says anything — so
the dots can sit there for the better part of a minute. That is the wait
working, not a fault. If they disappear without an answer, or you are told it
could not reach the assistant, that one did fail.

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

## Signing in

Opening the display page on a machine that is not already a screen on somebody's
wall may give you a **sign-in box**: your email address and your password.

You will not always get one. It appears when this browser cannot use the
assistant on that address — either because signing in is required there, or
because it is limited to particular people and you are not yet one of them.
Where neither applies you get the assistant straight away and never see a box
at all. **So the same server can ask on one address and not on another**, and
that is deliberate: whether an assistant needs a sign-in is set per assistant,
not once for the machine.

You get those from an administrator, in two halves. They create the account
with your address and send you a **link**; opening it asks you to choose a
password, once. That link works exactly once and then it is spent — from then
on you sign in with the address and the password, on any machine, including one
that has never seen you before.

Nobody but you ever knows the password. An administrator cannot see it or set
it; if you forget it they send a new link and you choose another.

**A sign-in can lapse from quiet.** Where an administrator has set a limit, it
is measured as the gap *between conversations* — so a session you are using
never runs out, and one nobody has spoken into for long enough asks again.
Different assistants can be set differently, or not at all.

Under the sign-in box are two links for the two people who are not signing in:
**Use Code Instead**, for somebody hanging a screen, and **Request Access**, for
somebody asking to be let in. Each one swaps the box for the thing it names, and
offers the way back.

**If it says you do not have access**, your password worked and the assistant on
that address has not been granted to your account. There is nothing to try again
and nothing you did wrong: it is one tick on your row in the panel, and only an
administrator can make it.

## Signing out

**A SIGN OUT button** appears beside AUDIO and TEXT whenever somebody is signed
in. It asks first, naming who is about to be signed out, because on a machine
two people share the person pressing it may not be the person signed in.

**It ends this screen's session and no other.** If you are signed in on your own
laptop as well, that stays signed in — ending every session you have anywhere is
account recovery, and it is what a new link from an administrator does.

**There may also be a phrase**, if your administrator set one — something like
*sign me out*, alongside the sleep word. The two are not the same: the sleep
word ends the conversation and leaves you signed in; this ends the session.
Where a phrase is set, anybody in earshot can say it, which is the trade for a
screen on a wall being able to be left properly.

**Closing the tab signs you out too**, after about fifteen seconds — and so does
a browser that crashes, sleeps or loses the network, after three minutes of
silence. Reloading the page does not: that is the same browser still there, and
a sign-in that could not survive a refresh would be one nobody used.

## The date and time

Some screens carry the **date and time across the top**. Whether they do is set
per place — a wall people walk past wants it; a browser tab has a clock in the
corner already — and how it reads is set once for the whole deployment, so two
screens in a corridor never disagree about how to write the hour.

It reads **the device's own clock**, not the server's, so a tablet set to the
wrong time shows the wrong time. That is deliberate: it is the time in the room,
and a screen quietly showing a different one from every other clock around it is
worse than one that is visibly wrong. It stays visible while the screensaver
drifts, travelling with the figure rather than holding still.

## Setting a screen up with a code

If somebody has given you a **six-character code** — for a screen going on a
wall, a television, a tablet — open the display page on that device, press
**Use Code Instead**, and type the code into the box: *Setting this screen up?*

Case and dashes do not matter: `k7q-p4m` and `K7QP4M` are the same code. It
works once, and it is only good for ten minutes, so get it as you walk to the
screen rather than an hour before.

The screen restarts itself when it takes the code, and comes back as the
display it was named as — with whatever appearance and assistants were set up
for it before you ever switched it on.

You can also type `<this server>/e/CODE` straight into the address bar, which
is easier on a television with a remote and does the same thing.

## Asking for access

On some installations you have no account and no code — you are simply at a
machine that has not been given access to anything yet. Press **Request
Access** under the sign-in box.

If you were given a code, use **Use Code Instead** — that is a different thing
from asking, and it needs no decision from anybody.

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

## If it says it has lost its server

Any display shows **NO CONNECTION TO THE SERVER** high in the frame, and a
screen mounted on a wall also says it aloud, once. The figure carries on
drifting, because it is drawn on the device itself and never stopped — which is
exactly why the line is there. A screen that looks perfectly alive and is
reaching nothing would otherwise be walked past for a week.

There is nothing to press. It keeps trying on its own, the line disappears the
moment the server answers, and the screen reloads itself so it comes back with
anything that changed while it was down. If it is still saying it after a few
minutes, the server or the network between you and it needs somebody — tell
your administrator.

A screen you opened yourself in a browser does not say any of this out loud. It
stays quiet and tells you at the moment you actually ask it something, rather
than interrupting you about a server you were not using.

**Any display reloads itself when the server comes back**, and when a setting
it draws from changes — that is how a screen nobody is standing at stays
current. It waits until you have finished: nothing reloads while you are
talking to it or typing into the box.

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
