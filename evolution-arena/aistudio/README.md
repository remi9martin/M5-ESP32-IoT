# Evolution Arena for Google AI Studio

This is the same app as `../index.html`, plus a small `index.tsx` bridge. In AI Studio the bridge
calls Gemini with the key AI Studio already provides, so you can leave the key field empty.

## Put it in AI Studio
1. Run `./build.sh`, or use the committed `index.html` and the other files in this folder.
2. In AI Studio, open or create a Build app, then replace its files with these (or upload the zip).
3. Leave the API key empty, check the task, and press **Start**.

## Surviving timeouts and resets
- Progress autosaves to the browser after every iteration.
- **Auto-export save every N iters** downloads a `arena-save-iterN.json` file. Use **Export save**
  at any time, and **Import save** to continue exactly where you stopped, even on another machine.
  If the AI Studio preview blocks downloads, open the app in its own tab and export there.

## Keeping AI use low
- **Patch mode** (on by default): the AI returns only small find/replace edits. Plain code applies them,
  boots the page in a sandbox, checks for errors and measures it, and rolls back failures, all without AI.
- Each round costs 2 mutation calls plus 1 call per judge line, plus 1 red-team call only when a change wins.
- **Max API calls** stops the run at a hard budget. Screenshots are off by default.

## Run locally
`npm install`, put `GEMINI_API_KEY=...` in `.env.local`, then `npm run dev`.
