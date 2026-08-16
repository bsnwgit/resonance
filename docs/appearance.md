# Appearance & geometry

Everything here writes the shared settings document, so it changes what
**every** display shows. Move a control and the preview responds immediately;
nothing reaches anyone else until you press SAVE FOR EVERYONE.

There is no wrong setting in this document — none of it can break the app —
so the honest advice is to open the preview and push the sliders around.

## APPEARANCE

### Palette

BLUE, MILK, ICE, AMBER, RUST. Only the figure's colour channel changes — the
text stays fixed neutral white deliberately, so the transcript stays readable
no matter how dark the geometry goes.

### Layout

**HERO** gives the figure a defined area with the transcript below it.
**FULL BLEED** lets it fill the frame. Full bleed suits a wall display being
looked at; hero suits one being read.

### Form & size

| Control | Effect |
|---|---|
| amplitude | how far the figure moves for a given sound |
| lines | how many strands are drawn |
| layer phase | how far each strand lags the one before it |
| depth | separation front to back |
| spread | how far it opens out |
| perspective | how strongly depth foreshortens |

Two practical notes. **lines** is the main cost: if the display is a low-power
box and the frame rate drops, this is the first control to bring down. And a
high **amplitude** with a high **layer phase** is what produces the tangled
look — reduce one of the two rather than both.

### Glass

The surface treatment over the figure.

| Control | Effect |
|---|---|
| bloom | glow around bright lines |
| blur radius | how far that glow spreads |
| milk | a haze over the whole frame |
| grain | film-like noise |
| scanlines | horizontal banding |
| line weight | stroke thickness |

These are cumulative and easy to overdo. Bloom plus milk plus grain at once
turns a sharp figure into fog. If the display looks muddy, this is where to
look first.

## GEOMETRY

### Pattern

Four figures. They are genuinely different shapes rather than presets of one
shape, so try each rather than assuming.

| Mode | Reads as |
|---|---|
| STACK | layered horizontal waves — the most legible for speech |
| DISC | a rotating ring |
| ORB | a sphere of lines |
| KNOT | a closed looping curve |

STACK is the safest default: it maps most directly onto sound, so a viewer
learns what the movement means fastest.

### Rotation

**TURNTABLE** rotates about one axis at a steady rate — calm, predictable,
correct for something that is on a wall all day.

**FREE TUMBLE** re-aims itself periodically for a looser, less mechanical
feel. **re-aim every** sets how often, and **RE-AIM NOW** does it immediately
so you can see what a re-aim looks like without waiting.

| Control | Effect |
|---|---|
| spin (platter) | rotation about the vertical |
| tilt / view height | where you appear to be looking from |
| wobble | wander off the axis |
| roll / lean | tip to one side |
| master rate | scales all of the above at once |

**master rate** is the one to reach for. If the motion is distracting, halve
that rather than trimming four sliders.

### Spectrum

How sound becomes shape.

| Control | Effect |
|---|---|
| spike width | how sharp a peak is |
| spike decay | how quickly a peak falls away |
| body / swell | how much the whole figure responds to overall level |
| peak colour | how far the colour shifts at a peak |
| heat threshold | how loud a sound has to be to count as a peak |

If the figure looks frantic, raise **heat threshold** first — most of the time
the problem is that the room's background noise is clearing the bar.

### Noise floor

**static level** and **crackle** add a small amount of movement when there is
nothing to respond to. A completely still figure reads as broken, which is why
this exists; too much of it reads as noise. A little goes a long way.

## Test drive

Under SPEECH, not APPEARANCE, but it belongs in this workflow: **IDLE**,
**THINKING** and **SPEAK SAMPLE** drive the figure through each state without
needing a microphone or a real question. This is the fastest way to judge a
palette or a motion setting, because you can see all three states in a few
seconds rather than waiting for them to happen.

**token rate ms** controls how fast the sample is fed in, which approximates
a faster or slower assistant.
