# ThoughtFlow Assets

This directory contains branding and media assets for ThoughtFlow.

## Required Images

Please add the following images to complete the README:

### Logo Files

| File | Description | Recommended Size |
|------|-------------|------------------|
| `logo.png` | Main logo (fallback) | 840x420px or similar |
| `logo-light.png` | Logo for light mode backgrounds | 840x420px |
| `logo-dark.png` | Logo for dark mode backgrounds | 840x420px |

### Demo Media

| File | Description | Notes |
|------|-------------|-------|
| `demo.gif` | Terminal recording showing ThoughtFlow in action | Use [asciinema](https://asciinema.org/) or [terminalizer](https://terminalizer.com/) |

## Image Guidelines

### Logo Design Suggestions

- Keep it clean and minimal (reflects the library's philosophy)
- Consider incorporating:
  - A brain/thought bubble motif
  - Flow/stream visual elements
  - Python-inspired colors (blue/yellow) or your own palette
- Ensure good contrast for both light and dark backgrounds

### Demo GIF Guidelines

The demo recording should showcase:

1. **Installation:** `pip install thoughtflow`
2. **Import:** `from thoughtflow import LLM, MEMORY, THOUGHT`
3. **Basic workflow:** Creating an LLM, MEMORY, THOUGHT, and executing
4. **The magic moment:** `memory = thought(memory)`
5. **Getting results:** `memory.get_var("result")`

**Tools for creating terminal GIFs:**
- [asciinema](https://asciinema.org/) + [agg](https://github.com/asciinema/agg) (recommended)
- [terminalizer](https://terminalizer.com/)
- [vhs](https://github.com/charmbracelet/vhs) (Charm's VHS)

**Recommended settings:**
- Font: JetBrains Mono, Fira Code, or similar
- Theme: Dracula, One Dark, or custom
- Size: 80x24 terminal
- Speed: 1.5x - 2x playback
- Duration: 15-30 seconds max

## File Naming Convention

- Use lowercase with hyphens: `logo-dark.png`
- No spaces in filenames
- Use appropriate extensions: `.png` for images, `.gif` for animations, `.svg` for vectors

---

Once you've added your images, the README will automatically display them!
