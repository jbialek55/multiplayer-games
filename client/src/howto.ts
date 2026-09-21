/// "How to play" panels, shown on the game screen once you are in a game.
/// Only games that need an explanation have an entry.

interface HowTo {
  title: string;
  steps: string[];
}

const HOW_TO_PLAY: Record<string, HowTo> = {
  snake: {
    title: "How to play Snake Battle",
    steps: [
      "2–4 players share one board. Each of you steers a snake in your own colour; yours is shown in the header and on the countdown screen, and your head has a white frame.",
      "Steer by swiping your finger on the board in the direction you want to go (arrow keys work too). Your snake keeps moving on its own.",
      "Eat the cream-coloured dots to grow and score points.",
      "You can't turn straight back into yourself. Crash into a wall, your own body or another snake and you're out.",
      "The last snake alive wins. If everyone crashes at once, the higher score wins (then the longer snake).",
      "In a room, the host presses “Start game” once everyone has joined.",
    ],
  },
};

/// Fill a <details> element with the panel for `gameId` (or hide it). Rebuilt
/// only when the game changes, so a reader's open/closed choice survives the
/// constant re-rendering.
export function renderHowTo(el: HTMLDetailsElement, gameId: string, open: boolean): void {
  const info = HOW_TO_PLAY[gameId];
  el.hidden = !info;
  if (!info || el.dataset.game === gameId) return;
  el.dataset.game = gameId;
  el.open = open;
  const summary = document.createElement("summary");
  summary.textContent = info.title;
  const list = document.createElement("ul");
  info.steps.forEach((step) => {
    const li = document.createElement("li");
    li.textContent = step;
    list.appendChild(li);
  });
  el.replaceChildren(summary, list);
}
