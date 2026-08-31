---
hide:
  - toc
---

# Architecture

Interactive maps — pan, zoom, theme, and guided views. Use **Open fullscreen**
for a chrome-free viewer.

=== "Runtime"

    Entry → Context → TUI / CLI → `GitApi` → `git`. Observe attaches after start.

    [Open fullscreen](assets/archify/pigit-runtime.architecture.html){ target=_blank .md-button }

    <div class="archify-embed" markdown="0">
      <iframe
        class="archify-frame"
        src="../assets/archify/pigit-runtime.architecture.html"
        title="pigit runtime architecture"
        loading="eager"
        referrerpolicy="no-referrer"></iframe>
    </div>

=== "Sequencer"

    Merge / rebase / cherry-pick lifecycle: waits, recoverable continue, abort.

    [Open fullscreen](assets/archify/pigit-sequencer.lifecycle.html){ target=_blank .md-button }

    <div class="archify-embed" markdown="0">
      <iframe
        class="archify-frame"
        src="../assets/archify/pigit-sequencer.lifecycle.html"
        title="pigit sequencer lifecycle"
        loading="lazy"
        referrerpolicy="no-referrer"></iframe>
    </div>

Source: [`docs/archify/`](https://github.com/zlj-zz/pigit/tree/dev/docs/archify)
