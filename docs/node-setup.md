# Setting up a node

A **node** is a screen: a tablet on a wall, a television, a laptop, anything with
a browser. Getting one working is not one form. It is a chain, and every link
has to exist before the one after it can name it — which is why a node that
"does nothing" is almost always a link further back than the one being looked
at.

This is the whole chain, in the order you build it.

## The chain

```
  PROFILES ▸ MODELS            PROFILES ▸ NETWORK
  ┌──────────────────┐         ┌────────────────────────────┐
  │ what it speaks   │         │ IP address   ── binds      │
  │ to: provider,    │         │ Port         ── binds      │
  │ base URL, model, │         │ Address in links ── names  │
  │ key, limits,     │         │ Port in links    ── names  │
  │ system prompt    │         │ Plain HTTP redirect        │
  └────────┬─────────┘         └──────────────┬─────────────┘
           │                                  │
           └───────────────┬──────────────────┘
                           ▼
                 PROFILES ▸ CONNECTION
                 ┌────────────────────┐
                 │ one model +        │
                 │ one network,       │
                 │ under one name     │
                 └─────────┬──────────┘
                           │
   PROFILES ▸ LAYOUT       │     PROFILES ▸ AUTHENTICATE   ▸ AUTHORIZE
   ┌──────────────────┐    │     ┌─────────────────┐  ┌──────────────────┐
   │ names an         │    │     │ must there be   │  │ ANY DISPLAY, or  │
   │ appearance,      │    │     │ a person, and   │  │ ONLY THESE + the │
   │ geometry, speech │    │     │ how long a      │  │ ticked screens,  │
   │ and screensaver  │    │     │ session lasts   │  │ people, groups,  │
   │ + kiosk, clock,  │    │     └────────┬────────┘  │ embeds           │
   │ fullscreen…      │    │              │           └────────┬─────────┘
   └────────┬─────────┘    │              └──────┬─────────────┘
            │              │                     ▼
            │              │           PROFILES ▸ PERMISSION
            │              │           ┌────────────────────┐
            │              │           │ one authenticate + │
            │              │           │ one authorize      │
            │              │           └─────────┬──────────┘
            │              │                     │
            └──────────────┼─────────────────────┘
                           ▼
                    EndPoints ▸ AI
                    ┌───────────────────────────┐
                    │ THE ENDPOINT              │
                    │ name · wake word          │
                    │ names one connection      │
                    │ names one layout          │
                    │ names one permission      │
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────────────────┴──────────────────────────┐
        ▼                                                    ▼
  SETTINGS ▸ ENROLL                              ENROLLMENTS ▸ DEVICE
  ┌────────────────────────────┐                 ┌──────────────────────┐
  │ Enroll Network ▸ Device    │                 │ name the node        │
  │   interface + port         │                 │ GET A CODE           │
  │ Enroll URL ▸ Device        │                 │ tick the endpoint    │
  │   Address in links         │                 │   ← this is the grant│
  │ Enroll Time Limit ▸ Device │                 └──────────┬───────────┘
  │   how long a code lasts    │                            │
  └─────────────┬──────────────┘                            │
                └──────────────────┬─────────────────────────┘
                                   ▼
                        ┌────────────────────────┐
                        │ AT THE SCREEN          │
                        │ open the device door   │
                        │ type the six           │
                        │ characters             │
                        └───────────┬────────────┘
                                    ▼
                        ┌────────────────────────┐
                        │ registered, and sent   │
                        │ on to the first        │
                        │ endpoint it may use    │
                        └────────────────────────┘
```

## What each link is for

**A model profile** is what an assistant speaks to — a provider, an address, a
model name, a key, the limits and the system prompt. Several endpoints can name
one.

**A network profile** is where an assistant answers. It carries four things and
they are two different questions. **IP address** and **Port** are a *binding*:
which interface this server listens on, and on which port. **Address in links**
and **Port in links** are a *name*: what goes in front of the port in every URL
this server builds for that profile. Behind a reverse proxy those differ by
definition — the listener answers on its own port and the world arrives at a
name on 443 — and **a blank Port in links means none**, the scheme's own. Leave
the name empty and links are built from the binding, exactly as they always
were.

**A connection** is a model and a network under one name. It is the pair an
endpoint picks, so that "what it speaks to" and "where it answers" are chosen
once rather than on every endpoint that wants the same combination.

**A layout profile** is what the screen looks like: it names an appearance, a
geometry, a speech profile and a screensaver rather than carrying copies, so
changing what a hallway looks like once reaches every screen using it. The
speech profile is where the assistant's **name and wake word** live — what it is
called is part of how it sounds.

**An authenticate profile** answers whether there has to be a person at all.
**An authorize profile** answers which of them. A **permission** is the pair,
and an endpoint names one.

**An endpoint** is the assistant: a name, a wake word, and one of each of the
three above.

## The rules that bite

**One endpoint per port.** A network profile carries one endpoint, always. If a
new endpoint's connection picker offers nothing but NONE, every network profile
you have already has an endpoint answering on it — make another profile with a
free port. The row says so under the picker.

**The layout comes from the port.** A port carries one endpoint and an endpoint
names one layout, so opening that address in *any* browser — with a device token
or without one — shows that endpoint's appearance, greeting and name.

**An authorize profile is the grant, and it can be shared.** Two endpoints
naming one profile share the screens ticked on it. Tick one and not the other
and the profile is **split** — the endpoints you ticked get their own copy, so
the tick means what it says. The row tells you when that happened.

**A code is spent at one door.** With a device enrolment port set, that address
is the only place a code works and the six characters answer 404 everywhere
else. With no port set, a code is typed at whichever display listener answers.

**Ports and interfaces need a restart; names do not.** Address in links, Port in
links and the enrolment names are read at the moment a link is built. The tab's
pending line at the foot says when a restart is owed.

## Order of work

1. **PROFILES ▸ MODELS** — make the model.
2. **PROFILES ▸ NETWORK** — make the network profile. Give it a free port, and
   an Address in links if anything sits in front of this server.
3. **PROFILES ▸ CONNECTION** — pair them.
4. **PROFILES ▸ LAYOUT** — make the layout, and the appearance, geometry and
   speech it names.
5. **PROFILES ▸ AUTHENTICATE / AUTHORIZE / PERMISSION** — decide who.
6. **EndPoints ▸ AI** — make the endpoint and name the four.
7. **Restart** if you added or moved a port.
8. **SETTINGS ▸ ENROLL** — set the device door once, for the whole deployment.
9. **ENROLLMENTS ▸ DEVICE** — name the node, tick its endpoint, GET A CODE.
10. **At the screen** — open the device door and type the code.

## When it does not work

**The screen shows the wrong assistant's look or name.** The layout comes from
the port. Check that the endpoint on that port names the layout you meant, under
EndPoints ▸ AI.

**The screen was sent somewhere unexpected after enrolling.** It goes to the
*first* endpoint it may use. If something you did not tick is in that list, an
authorize profile is shared — see above.

**A link says an IP and a port.** The network profile has no Address in links,
so the binding is being used as the name.

**A link says a name and the wrong port.** The network profile has an Address in
links but Port in links is set to the bind port. Behind a proxy it should be
blank.
