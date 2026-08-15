# Kryon personal web dashboard

This is a standalone, single-file web dashboard built for a personal Kryon demo.

## Layout & Features

1. **Chat (Home) Page**:
   - A welcoming cartoon orange octopus mascot peeking over the top card row.
   - On page load, the mascot pops out from behind the black chat box and settles into a gentle scaling "breathing" animation.
   - Gemini-powered chat input: Pasting a prompt in the input calls Google Gemini API (using the key configured in Settings) and appends the markdown-rendered response.
   - Status indicators (uptime, low threat level concentric radar visual).
   - Tactical feeds showing logs with timestamps.
   - System Status card with an animated pulsing wave.
   - Active agent list (1 running, 2 idle).
   - **No specific security tool names are listed anywhere on the page** (e.g. the Tools card shows only a count).

2. **Testing Mode Page**:
   - An interactive 8-tentacle octopus layout.
   - The head is positioned in the center, and 8 SVG curvy tentacles connect to 8 cube-eye agent nodes.
   - Cube agents have blinking eye animations. Hovering over a node highlights its tentacle path and displays its state.
   - Clicking "**▶ Start test run**" executes a sequential simulation where each agent glows in green, bounces, and prints step-by-step progress logs to the side terminal console.

3. **Settings Page**:
   - Save your Google Gemini API Key in `localStorage`.
   - Test Connection button to verify the key works (success and error states shown inline).
   - Animation toggle preferences.

## How to Run

### Option 1: Open Directly in Browser
Double-click `index.html` in this folder to open it in Chrome, Edge, Firefox, or Safari.

### Option 2: Run a Local HTTP Server
Run the following command in this directory:
```bash
python -m http.server 8000
```
Then navigate to `http://localhost:8000` in your web browser.

## Configuration

1. Go to **Settings** in the sidebar.
2. Enter your Google Gemini API Key (you can get one at [Google AI Studio](https://aistudio.google.com/apikey)).
3. Click **Save Settings**.
4. Click **Test Connection** to verify it is working.
5. Go to **Chat** page and enjoy talking to KRYON!
