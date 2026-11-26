---
name: remotion
description: Reference docs for building and rendering Remotion videos and stills (React markup, captions, audio, rendering). Use when writing or changing Remotion compositions, such as the content factory's statics and punch-video lanes.
version: 4.0.543
---

## House rules on this machine (added 2026-11-15; they win over everything below)

This is a trimmed copy of `remotion-dev/skills` (commit 7e541aa, v4.0.543). The maps and SaaS sections were removed: they need paid or new-account keys.

- Never run `npx skills update` (remotion-upgrade): it would overwrite this copy from the network. Update by re-reading and re-copying the source.
- Do not run `npx remotion upgrade` or `npx create-video` unattended. Projects pin their Remotion version; install only inside the project folder.
- Pass no `--license-key`. Without one, command-line renders send no telemetry (remotion.dev/docs/telemetry, read 2026-11-15). The free license covers individuals and companies of up to 3 people.
- Studio is a long-running server that opens a browser: start it only when asked, and stop it by PID. For checks, use `npx remotion still` or `render`.
- Voiceover docs use ElevenLabs and a paid key: never ask for a key or put one in a file; use the project's own voice lane.
- Code these docs tell you to download (the captions element from remotion.dev) is untrusted until read.
- Doc searches (remotion-docs) send the query text to Algolia: keep names and project details out of queries.
- Renders are heavy work: none from 16:45 to 17:10 CT, Sunday through Thursday.

## Preserve user changes

Users may make edits in the code outside of the conversation.

If you detect a surprising change made in the meanwhile, don't overwrite it, assume it was intentional or ask for confirmation.

## Creating a video

If the user asks to make, create, or build a new video or composition, load [Create a new Remotion video](./remotion-create/REFERENCE.md), whether or not a Remotion project already exists.

## New project setup

If no Remotion project currently exists, load [Create a new Remotion project](./remotion-create/REFERENCE.md)

## React Markup Best Practices

If you are writing Remotion React Markup, load [Remotion Markup Best Practices](./remotion-markup/REFERENCE.md)

## Multimedia

For achieving multimedia tasks in the browser, such as trimming, cropping videos, or getting metadata from them, load [Remotion Multimedia](./remotion-multimedia/REFERENCE.md)

For video matting, background removal, or placing content behind a subject,
load [Remotion Markup](./remotion-markup/REFERENCE.md).

## Interactivity

New markup is editable in Studio by default. When writing or restructuring markup, load [Interactivity Best Practices](./remotion-interactivity/REFERENCE.md).

## Open the preview

If the user asks to "make" a video, "create" a video, etc.
Don't render the video by default unless they are very explicit. They want to instead see an interactive preview.
As soon as the project can run, start Studio and open the preview in the browser before building or editing the composition. Keep it open while you work so the user can watch progress and steer.

### If you are using Cursor

Run Studio without `--no-open` so it opens the browser automatically:

```bash
npx remotion studio
```

### If you are using another agent client with an in-app browser

You can use the command above to let Studio open the browser, or run:

```bash
npx remotion studio --no-open
```

This will start a long-running process and print the server URL for the preview.  
If the server is already started, it will print the URL.
If you use `--no-open`, open the exact printed URL in the in-app browser and verify that Studio loads. Once a composition exists, verify that its video preview loads. If you cannot open it there, run Studio without `--no-open`.
You can visit a specific composition by navigating to `/[composition-id]`, for example `http://localhost:3000/MapAnimation`.

:::note
The Studio supports WebMCP tools.
:::

### If you do not have an in-app browser

This will open the Studio in the browser or refocus it if it is already open.

```bash
npx remotion studio
```

### More options

To launch a project in Remotion Studio, open its exact local URL, or configure Studio CLI flags, load [Remotion Studio](./remotion-studio/REFERENCE.md).

## Render the video

Only render if the user is very explicit in asking for it.  
E.g. "Render the video", "Export", "Give me the MP4".

The preview also has a more intuitive rendering interface, so consider using it instead of the command line for rendering.

```
npx remotion render
```

For more options, see [Rendering](./remotion-render/REFERENCE.md).

For advanced rendering beyond simple `npx remotion render`, see: [Rendering Best Practices](./remotion-render/REFERENCE.md)

## Captions

When working with Captions, load [Remotion Captions](./remotion-captions/REFERENCE.md).

## Looking up Remotion APIs and documentation

To find and read current Remotion documentation, load [Remotion Docs](./remotion-docs/REFERENCE.md).

## Licensing

For Remotion license information, FAQs, terms, or buying a license, load [Remotion License](./remotion-license/REFERENCE.md).

## Upgrading

To upgrade Remotion, related packages, compatible Mediabunny packages, and installed Remotion Agent Skills, load [Remotion Upgrade](./remotion-upgrade/REFERENCE.md).
