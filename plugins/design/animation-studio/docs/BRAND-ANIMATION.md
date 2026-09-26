# Default Animation Language

## Personality

These defaults suit a professional product: animations are **precise and purposeful**. They guide attention and communicate hierarchy; they never exist for decoration. If the brand is deliberately playful, adjust bounce and timing, and keep the accessibility rules below unchanged.

If the project defines its own motion tokens (durations, curves), use those instead of this file.

## Timing Scale

| Context | Duration | Notes |
|---------|----------|-------|
| Micro-interaction (button press) | 100-200ms | Instant feedback |
| UI element enter | 300-500ms | Smooth but quick |
| Section enter (scroll) | 400-600ms | Noticeable, not slow |
| Stagger delay | 80-120ms | Between sibling elements |
| Page transition | 300-400ms | Cross-fade or slide |
| Video scene transition | 500-1500ms | Cinematic feel |
| Video CTA hold | 3000ms minimum | Must be readable on autoplay |

## Easing

### Motion (React)
```
type: "spring"
visualDuration: 0.4
bounce: 0.15
```

### anime.js
```js
import { cubicBezier } from 'animejs'

ease: cubicBezier(.4, 0, .2, 1)
```

Pass the function, not a string: anime.js v4 ignores `ease: 'cubicBezier(...)'` with a warning and runs linear.

### CSS and Web Animations API
```css
transition-timing-function: cubic-bezier(0.4, 0, 0.2, 1);
```

### Avoid
- `linear` (except progress bars and continuous spinners)
- `bounce` > 0.3 (too playful for a professional product)
- `elastic` easing (too dramatic)

## Motion Vocabulary

### Enter (most common)
- **Fade up**: `opacity: 0→1, translateY: 20px→0` (default for everything)
- **Scale in**: `opacity: 0→1, scale: 0.95→1` (emphasis elements, badges)
- **Slide in**: `translateX: ±20px→0, opacity: 0→1` (directional context)

### Exit (only when element leaves DOM)
- Reverse of enter, at 0.6× duration
- Fade down: `opacity: 1→0, translateY: 0→10px`

### Hover
- **Card lift**: `translateY: 0→-4px` + shadow increase
- **Button scale**: `scale: 1→1.03`
- **Link underline**: CSS transition (not JS)

### Tap/Active
- **Button press**: `scale: 1→0.97`

### Scroll
- **Parallax**: subtle, max 20px offset (never jarring)
- **Stagger children**: 80-120ms between items, max 6 items

## Color in Animation

- Animate `opacity` and `transform` only (GPU composited, 60fps)
- Never animate `color`, `background-color`, `border-color` in a JS loop (triggers repaint)
- Exception: hover color transitions are fine via CSS (handled by browser efficiently)
- Colours themselves come from the project's tokens, never hardcoded

## Accessibility

Every animation must:
1. Check `prefers-reduced-motion`: disable transforms, keep opacity transitions (ambient loops stop entirely)
2. Not convey critical information solely through motion
3. Not flash or strobe (WCAG 2.3.1)
4. Have a static fallback state that looks intentional (not broken)
