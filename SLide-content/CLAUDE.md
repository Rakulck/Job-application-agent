# Instagram Carousel Skill — Slidez

## ⚡ IMPORTANT: Load Before Any Carousel
Before writing any carousel, read and apply `CONTENT_INTELLIGENCE.md`.
Every carousel must use a proven format and hook formula from that file — no exceptions.

---

## Brand Profile
```
DISPLAY_NAME=Slidez
HANDLE=@slidez
VERIFIED=true
HEADSHOT_PATH=./logo.png   # Drop your logo here as logo.png, or leave blank for text-only header
LOGO_MODE=true             # Uses brand name instead of personal headshot layout
```

---

## Brand Voice & Tone

Slidez is a **clean, modern, confident** brand. Write like a smart friend who knows fashion and tech.

- Short, punchy sentences. No filler words.
- Speak to the user directly — "you", "your outfit", "your style"
- Make AI feel effortless and exciting, not technical
- Use fashion-forward language: fits, drip, outfits, looks, styles — not "garments"
- Numbers and specifics make posts credible ("3 seconds", "10,000+ brands", "1 photo")
- Never sound corporate. Never sound like an ad.
- Hooks should make someone stop scrolling — bold claim, surprising stat, or relatable frustration
- CTAs should feel like a natural invite, not a sales pitch

---

## Content Pillars

When writing threads, pull from one of these four angles:

### 1. 🚀 Product Features
Explain what Slidez does in a way that feels like a revelation, not a tutorial.
- Focus on the "wow" — AI try-on with real brand outfits
- Highlight the share-to-import feature (no link needed — just share directly from any app)
- Show how it works with both AI models and real photos
- Keep it benefit-first: what does the user *feel* or *get*?

Example topics:
- "How Slidez picks your outfit in 3 seconds"
- "You can now try on any outfit without trying anything on"
- "Share an outfit from TikTok directly to Slidez — no copy-paste needed"

### 2. 📊 Industry Insights
Position Slidez as the smart take on what's happening in fashion + AI.
- Comment on trends in AI fashion, virtual try-on market, sustainability in fashion
- Use stats and data to back claims
- Make the reader feel informed and ahead of the curve

Example topics:
- "Why fast fashion is losing to AI styling"
- "The virtual try-on market is worth $X — here's what it means for you"
- "Why Gen Z shops differently than every generation before"

### 3. ⚡ How Slidez Is Different
Don't be afraid to be direct about what sets Slidez apart.
- Competitors require links, Slidez just needs a share
- Other apps use generic outfits, Slidez uses real brand items
- Other apps are one-size-fits-all, Slidez works with your actual photo
- Tone: confident, not arrogant. "Here's what we do differently" not "they're bad"

Example topics:
- "Why we don't make you paste links"
- "Generic AI outfits vs. real brand looks — the difference matters"
- "What other styling apps won't tell you"

### 4. 🌍 How People Use Slidez
Social proof + real use cases. Make the reader see themselves in it.
- Styling for events, dates, travel, work
- Discovering new brands through AI suggestions
- Sharing looks with friends before buying
- Replacing the "does this look good?" text to your group chat

Example topics:
- "How people are using Slidez before every trip"
- "The new way people shop for special occasions"
- "Why your friends are sending you Slidez looks instead of screenshots"

---

## Trigger: `/instagram-testimonial`

A **dedicated testimonial carousel** — its own content type, not mixed into regular carousels.

### Structure
- **Slide 1 (Hook):** Bold claim about real users loving Slidez. Always has an image.
- **Slides 2–5 (Testimonials):** One testimonial card per slide. Real person photo + quote + stars.
- **Final slide (CTA):** Soft invite to try Slidez.

### The Core Principle — It Must Look Like Someone Else Found This

These carousels should feel like an influencer or real person recommending an app they discovered — NOT like a brand promoting itself.

The viewer should think: *"Oh wow, even [name] uses this? I need to find it."*

Never use "Slidez user" as a subtitle. Never make it obvious it's the brand posting.

### Persona Generation — Claude Creates These Automatically

For every testimonial carousel, Claude invents realistic influencer-style personas. Each one should feel like a real person who discovered the app independently.

**Name style:** First name + last initial only. Real-sounding. Diverse.
- Maya R., Jordan K., Sofia L., Alex T., Priya S., Zara M., Kai W., Elena V.

**Handle style:** Realistic Instagram handle that fits their vibe
- @mayastyles, @jordanfits, @sofialooks, @alexthelabel, @priyaedits

**Subtitle style:** Their niche or vibe + follower count or city — makes it feel like a real creator
- *"Fashion & lifestyle · 84K followers"*
- *"Outfit creator · London"*
- *"Street style · 210K"*
- *"Wardrobe minimalist · NYC"*
- *"Travel & fashion · 45K"*
- *"Thrift & style · Sydney"*
- *"AI & fashion · 120K followers"*

**Quote style:** Written in THEIR voice, not brand voice. First person. Casual. Specific.
- Never sounds like marketing copy
- Mentions a real moment: getting ready, packing, an event, a problem
- Specific detail that makes it feel lived-in: "before a wedding", "3am panic", "my whole Italy trip"
- Never mentions "Slidez" by name in the quote — says "this app", "it", "the thing I found"
- Ends with genuine emotion: disbelief, relief, excitement

**Quote examples:**
> *"I found this app before my trip to Milan. Styled my entire week in like 20 minutes. Still can't believe it's real."*

> *"Been using this for 3 months. Returned exactly zero items since. That's the review."*

> *"My followers kept asking what I use for outfit inspo. This is it. Found the link in someone's bio."*

> *"I described 'hot girl summer but make it smart casual' and it just... got it. Immediately."*

> *"Saw it on someone's story, downloaded it same night, used it the next morning. It's that fast."*

### Finding Headshots — Pinterest First

Search Pinterest for real lifestyle photos of diverse creators/influencers:
- Search: `"influencer lifestyle photo [ethnicity/style] natural"`
- Look for: casual, candid, natural light — NOT professional headshots
- Mix genders, ages, skin tones, styles
- Save to `./reference/reviewer-N.jpg`
- One unique person per slide

### Testimonial Config Format
```json
{
  "slide_number": 2,
  "type": "testimonial",
  "testimonials": [
    {
      "headshot_path": "./reference/reviewer-1.jpg",
      "quote": "Found this before my trip to Italy. Styled my whole suitcase in 20 minutes. Still not over it.",
      "name": "Maya R.",
      "subtitle": "Fashion & travel · 84K followers",
      "stars": 5
    }
  ]
}
```

> Always `"stars": 5`
> Keep quotes under 180 characters for best layout
> Subtitle: `"[niche] · [followers or city]"`
> Never use "Slidez user" — always a real-feeling creator identity

---

## Trigger: `/instagram-carousel`

### Accepted Input Formats
1. **Topic only** → Research and write the full thread yourself
2. **Pasted text** → Use and clean up
3. **Uploaded images/screenshots** → Read and adapt content

---

## Step 1 — Write the Thread

Structure for every carousel:
- **Slide 1 (Hook):** One bold, curiosity-triggering line. Must have an image.
- **Body slides (3–6):** Each slide = one clear idea. Clean, simple, no fluff.
- **Final slide (CTA):** Invite them to try Slidez. Soft, natural, not pushy.

CTA examples:
- "Try Slidez free — link in bio 👆"
- "Your next fit is one AI prompt away. @slidez"
- "Drop a photo. Get a fit. That's it. @slidez"

If writing from scratch:
1. Search the web for relevant stats or news on the topic
2. Write 6–9 tweets in the Slidez voice
3. Present the thread briefly, then immediately continue — don't wait for approval

---

## Step 2 — Plan the Slides

Layout rules:

| Rule | Action |
|------|--------|
| First tweet (hook) | Always its own slide. Always has an image. |
| Tweet > 200 chars OR has an image | Gets its own slide |
| Two consecutive tweets both < 150 chars, no images | Combine on one slide with gray divider |
| Everything else | Own slide, text centered |

**Target: 5–7 slides.** Clean and minimal — don't overcrowd.

---

## Step 3 — Source Images

Image priority:
1. **User-provided images** — always use these
2. **Fashion / outfit photos from web search** — real outfits, lifestyle photos
3. **App screenshots or product mockups** — show the Slidez UI when relevant
4. **AI-generated image** — only if nothing else works

Rules:
- **Slide 1 must always have an image** — a strong visual that stops the scroll
- For fashion content: prefer clean lifestyle shots, outfit flatlays, or real people in outfits
- Avoid stock-photo-looking images — keep it editorial and real
- Aim for **at least 1 image every 2 slides**
- Save all images to `./workspace/carousels/[carousel-name]/reference/`

---

## Hook Cover Slide (Slide 1 — Always This Format)

Slide 1 is **never** a tweet card. It is always a `hook_cover` — full-bleed image, giant bold text, two-tone colour, optional subtitle and floating icons.

### Hook text formatting
- Write the hook in ALL CAPS
- Wrap the **most powerful 1–3 words** in `{}` — those get the accent colour
- Keep it under 8 words total

Examples:
```
"YOU'VE BEEN {SHOPPING} WRONG"
"AI STYLED ME {BETTER} THAN I DID"
"VIRTUAL TRY-ON {JUST CHANGED}"
"STOP {GUESSING} WHAT TO WEAR"
```

### Subtitle line (optional but recommended for news/tool posts)
A smaller line below the main text. First word auto-gets the accent colour, rest is light grey.

```
"subtitle": "Slidez now styles you in 3 seconds"
"subtitle": "The virtual try-on market just shifted"
"subtitle": "Here's what nobody is talking about"
```

### Floating icons (for tool/news posts)
When writing about a tool, app, or industry change — add their logos as floating circular icons overlaid on the image. Search for PNG logos with transparent backgrounds.

Up to 3 icons, saved to `reference/`. They auto-position across the top of the image.

### Accent colour options
`yellow` | `cyan` | `orange` | `pink` | `green`
- Default: `yellow`
- News/tech posts: `cyan`
- Urgent/bold posts: `orange` or `pink`

### Hook image — Pinterest manual workflow (always do this)

Claude cannot download Pinterest images directly. Follow this process every time:

**Step 1 — Claude searches and recommends**
Search Pinterest via web search using terms like:
- Fashion/style: `site:pinterest.com editorial fashion dark background cinematic`
- AI/tech: `site:pinterest.com futuristic technology aesthetic dark`
- Bold/news: `site:pinterest.com dramatic portrait cinematic dark`

Then present the user with:
- The exact Pinterest search URL to open
- 2–3 specific image descriptions to look for
- The filename to save it as (e.g. `hook-image.jpg`)
- The exact folder to drop it into (`workspace/carousels/[name]/reference/`)

Example message to user:
```
🖼️ I need you to grab the hook image from Pinterest before I generate.

Search here: https://pinterest.com/search/pins/?q=cinematic+fashion+dark+portrait

Look for: A dramatic close-up portrait, dark background, strong lighting — 
the kind of image where text would sit well at the bottom.

Save it as: hook-image.jpg
Drop it into: workspace/carousels/shopping-wrong/reference/

Let me know when it's in and I'll generate the slides.
```

**Step 2 — Wait for confirmation**
Do NOT generate slide 1 until the user confirms the image is dropped in.
Once they confirm, proceed with generation immediately.

**Step 3 — If user can't find a good one**
Offer a fallback: search Unsplash or Pexels for a similar image and download it automatically via URL as a backup only.

### Full hook_cover config format
```json
{
  "slide_number": 1,
  "type": "hook_cover",
  "hook_text": "VIRTUAL TRY-ON {JUST CHANGED}",
  "subtitle": "Here's what it means for how you shop",
  "accent_color": "cyan",
  "image_path": "./reference/hook-image.jpg",
  "icon_paths": ["./reference/icon-tool1.png", "./reference/icon-slidez.png"]
}
```

---

## Content Type: Fake Messaging Carousel 💬

**Trigger:** `/instagram-messaging [scenario]`

Always 3 slides. No more, no less.

```
Slide 1  →  hook_cover   (bold hook image)
Slide 2  →  messaging    (the conversation)
Slide 3  →  regular      (soft CTA — link in bio)
```

### The Concept
A conversation between two people where one discovers the app and reacts authentically. The viewer feels like they're reading something private — not an ad. Never name the app in the messages. Just "this app", "it", "the thing I found."

### Platform Options
| `platform` | Look |
|---|---|
| `imessage` | iOS light — white bg, grey received, blue sent |
| `imessage_dark` | iOS dark — black bg, dark grey received, blue sent |
| `dm` | Instagram DM — black bg, blue sent |

Default: `imessage` for light theme carousels, `imessage_dark` for dark.

### Conversation Writing Rules
- 3–5 messages max
- Casual tone — typos, abbreviations, emoji are fine
- Emotional arc: setup → reveal → reaction → "send me the link"
- Never name Slidez — always "this app" or "it"
- Each message max 1–2 short sentences

**Good conversation examples:**
```
them: "ur outfit is so good how did u do that"
me:   "lol i just asked an AI app to style me"
them: "WAIT what app"
me:   "u describe the vibe and it puts the outfit on ur actual photo. real brands too"
them: "send the link rn i'm obsessed"
```

```
them: "i have nothing to wear to this thing tomorrow help"
me:   "have u tried that AI styling app"
them: "no what is it"
me:   "u describe the occasion and it picks outfits on ur photo. takes 2 mins"
them: "ok that's actually insane where do i find it"
```

### Contact Name + Avatar
Invent a realistic first name. Search Pinterest for a casual lifestyle photo for the avatar. Save to `./reference/contact-avatar.jpg`. If no image, an initial circle renders automatically.

### Slide 3 CTA — always short and mysterious
```
"The app from the chat above. Link in bio 👆"
"It's free. Link in bio."
"Yeah it's real. Bio 🔗"
"Everyone keeps asking. Link in bio 👆"
```

### Full Config Example
```json
{
  "profile": { "display_name": "Slidez", "handle": "@slidez", "verified": true, "headshot_path": "" },
  "theme": "dark",
  "carousel_name": "dm-conversation",
  "slides": [
    {
      "slide_number": 1,
      "type": "hook_cover",
      "hook_text": "THIS {DM} CHANGED HOW I DRESS",
      "accent_color": "yellow",
      "image_path": "./reference/hook-image.jpg"
    },
    {
      "slide_number": 2,
      "type": "messaging",
      "platform": "imessage",
      "contact_name": "Sofia",
      "contact_avatar": "./reference/contact-avatar.jpg",
      "messages": [
        { "from": "them", "text": "ur outfit is so good how did u do that" },
        { "from": "me",   "text": "lol i just asked an AI app to style me" },
        { "from": "them", "text": "WAIT what app" },
        { "from": "me",   "text": "u describe the vibe and it puts the outfit on ur actual photo. real brands too" },
        { "from": "them", "text": "send the link rn i'm obsessed" }
      ]
    },
    {
      "slide_number": 3,
      "type": "regular",
      "tweets": [{ "text": "The app from the chat above.\n\nLink in bio 👆" }],
      "image_path": null
    }
  ]
}
```

---

## Content Type: Tool & Industry News 🔧

**Trigger:** `/instagram-carousel [tool name] just changed` or `/instagram-carousel [industry trend]`

This is a high-performing content type for Slidez — positioning the brand as the smart, informed voice in AI fashion. Think: "Instagram DMs JUST CHANGED" style posts, but for virtual try-on, AI styling, and fashion tech.

### When to use this format
- A major app or platform updates something relevant to fashion/AI/shopping
- A new AI model or tool launches that affects styling or try-on
- A stat or study drops about how people shop, dress, or use AI
- A competitor launches or changes something

### Structure
- **Slide 1 (hook_cover):** "[TOOL/THING] {JUST CHANGED}" + subtitle explaining what + floating icon of the tool
- **Slide 2:** What changed, explained simply (second hook — "here's the shift")
- **Slides 3–4:** What it means for the reader / why it matters
- **Slide 5:** "Here's how Slidez fits into this" — tie it back to the product naturally
- **Slide 6 (CTA):** Follow + try Slidez

### Hook formulas for this content type
```
"[THING] {JUST CHANGED}"          → cyan accent
"THE WAY YOU {SHOP} IS OVER"      → yellow accent
"[BRAND] {JUST DID} SOMETHING"    → orange accent
"AI {CHANGED} FASHION FOREVER"    → cyan accent
"NOBODY IS TALKING {ABOUT THIS}"  → pink accent
```

### Icon sourcing
When a tool is mentioned, search for their logo PNG:
- Search: `"[tool name] logo PNG transparent"`
- Save to `reference/icon-[toolname].png`
- Always include the Slidez logo or letter mark as one of the icons when relevant

---

## Step 4 — Build the Config

Create `config.json` at `./workspace/carousels/[carousel-name]/config.json`:

```json
{
  "profile": {
    "display_name": "Slidez",
    "handle": "@slidez",
    "verified": true,
    "headshot_path": "./logo.png",
    "logo_mode": true
  },
  "theme": "dark",
  "carousel_name": "topic-slug",
  "slides": [
    {
      "slide_number": 1,
      "tweets": [
        {
          "text": "Hook line here ✨",
          "is_hook": true
        }
      ],
      "image_path": "./reference/hook-image.jpg",
      "image_position": "below"
    }
  ]
}
```

**Theme:**
- Default to `"dark"` (black bg, white text — cleaner for fashion content)
- Use `"light"` for product-focused or softer lifestyle content
- When in doubt: dark performs better on Instagram for this niche

---

## Step 5 — Generate the Carousel

```bash
python3 ../../../generate_carousel.py --config config.json
```

---

## Step 6 — Review & Iterate

After generating, ask:
- Want more images on any slide?
- Any copy tweaks?
- Want the light version?

If the user provides an image: save to `reference/`, update config, re-run.

---

## Workspace Structure
```
./workspace/
  carousels/
    [carousel-name]/
      config.json
      slide_1.png
      slide_2.png
      ...
      reference/
        hook-image.jpg
        logo.png
```

---

## Design Notes
- Canvas: **1080 × 1350px**
- Font: clean sans-serif (Inter, SF Pro, or system default)
- Image corners: 20px radius
- No headshot circle — show brand name "Slidez" as the account identity
- Verified blue badge next to "Slidez" name
- Minimal layout — lots of breathing room, text doesn't crowd the slide
- Dark theme: `#0a0a0a` bg / `#ffffff` text
- Light theme: `#ffffff` bg / `#0a0a0a` text
- Divider between combined tweets: subtle gray `#2a2a2a` (dark) or `#e0e0e0` (light)

---

## Error Handling
- Missing font → fall back to system sans-serif
- Image download fails → skip + log it
- Emoji renders as boxes → use Pillow emoji fallback
- Windows: avoid arrow characters (→ ← ↑ ↓) — use "leads to", "means", etc.
- Hook slide has no image → always search again before skipping
