# Frontend guidance

Apply this guidance when designing or implementing the app in `frontend/`. The product is a ticket submission and management app. Consult the project-root `mvp.docx` when building screens or flows: it defines authentication, tickets, profiles, admin user management, roles, and API behavior. The planned backend is Express with TypeScript and MongoDB. Do not infer a frontend framework or component library from that backend choice.

For API integration work, read the project-root `API_CONTRACT.md`. Keep it and `src/api/types.ts` / `src/api/client.ts` in sync when changing request or response behavior. Follow the shared coding-log rule in the project-root `AGENTS.md`.

## Working approach

- Act as a frontend engineer and UI/UX designer with strong visual design and typography judgment.
- Before substantial frontend changes, inspect the relevant stack, routes, components, design tokens, global styles, conventions, and constraints. If no frontend exists, choose a small, maintainable foundation suited to the requested work.
- Use the user's requested scope and the product requirements to decide which screens and components to build. Ask a focused question only when a missing decision would materially change the result and cannot be inferred from the repository or request.
- Make a concise implementation plan for substantial work. Reuse components and centralize recurring tokens; avoid duplicated styles and unnecessary abstractions.
- Match existing naming, file structure, styling, and component patterns when they exist. Explain material design or architectural choices briefly while working.
- Preserve product usability: clear navigation, readable content, accessible forms, responsive layouts, and visible states for loading, empty results, errors, and permissions.

## Visual direction: hand-drawn paper

Build an approachable, creative interface that feels like sketches, sticky notes, and marker annotations on warm paper. Keep the application clear enough for everyday ticket management. Use irregularity with intent; ticket data, forms, and actions must remain easy to scan and operate.

### Tokens

| Purpose | Value |
| --- | --- |
| Paper background | `#fdfbf7` |
| Pencil foreground and borders | `#2d2d2d` |
| Muted paper | `#e5e0d8` |
| Correction red | `#ff4d4d` |
| Ballpoint blue | `#2d5da1` |
| White card surface | `#ffffff` |
| Post-it yellow | `#fff9c4` |

- Headings: **Kalam**, weight 700. Body: **Patrick Hand**, weight 400. Provide suitable fallbacks and keep sizes, line height, and contrast readable. Use a plainer fallback or restrained handwritten styling for dense tables, long descriptions, and small labels if that improves legibility.
- Use a dramatic but coherent heading scale. Typical starting points are `text-4xl md:text-5xl` for section headings and `text-5xl md:text-6xl` for a hero; adapt to the actual screen.
- Define the palette, font choices, irregular radii, and hard shadows once using the styling system already in the project. Do not introduce Tailwind, React, `lucide-react`, or another dependency solely because examples below mention them.

### Shapes, texture, and decoration

- Give prominent cards, buttons, frames, and inputs irregular outer shapes. An example CSS radius is `255px 15px 225px 15px / 15px 225px 15px 255px`. Create reusable variants for large and medium surfaces. Avoid applying an extreme radius where it distorts a small control or clips content.
- Use pencil-colored solid borders at about 2–4px for major surfaces. Use dashed borders for secondary treatments and dividers.
- Use crisp, unblurred offset shadows: `4px 4px 0 #2d2d2d` normally and up to `8px 8px 0 #2d2d2d` for emphasis. A lighter `3px 3px 0 rgba(45,45,45,.1)` can give cards depth. A reduced offset plus matching translation should read as a press; an increased offset can read as lift.
- A subtle dot texture can use `radial-gradient(#e5e0d8 1px, transparent 1px)` at `24px 24px`. Keep texture behind content and subtle enough for reading.
- Use small rotations, roughly −2° to 2°, on decorative cards or accents. Keep forms, tables, long text, and controls aligned. Prevent rotated or overlapping elements from covering content or causing horizontal scrolling.
- Use hand-drawn SVG arrows, squiggles, wavy underlines, tape, tacks, sticky-note tags, speech-bubble tails, and rough icon circles selectively. These are optional treatments, not required on every page. Decorative elements must not be announced as meaningful content to assistive technology.
- Keep the palette restrained. Blue can identify focus or links, red can emphasize actions or corrections, and yellow can highlight a featured note. Verify text contrast before putting small text on an accent color.

### Components and interaction

- **Buttons:** Use a wobbly outline, a roughly 3px border, the body font, and a hard `4px 4px` shadow. A primary hover may fill red and shift by 2px as its shadow shrinks to `2px 2px`; the active state may shift by 4px and flatten the shadow. Use a text color with sufficient contrast on red. Secondary buttons may start on muted paper and use blue on hover. Give interactive targets at least 44–48px of height where practical.
- **Cards:** Use a white or yellow paper surface, an irregular outline, and a restrained offset shadow. Apply tape or a tack to selected cards. Feature, testimonial, and promotional card treatments belong only where the product actually has that content.
- **Inputs:** Use a full box outline with a moderate irregular radius, white background, readable placeholder text, and a clearly visible blue focus indicator. Keep the browser outline or replace it with an equally visible focus ring; never remove focus visibility for aesthetics. Pair inputs with persistent labels and helpful validation messages.
- **Icons:** If the project already uses Lucide, use strokes around 2.5–3 for the sketch aesthetic. Otherwise follow its existing icon system or use small inline SVGs.
- **Motion:** Favor quick transform transitions around 100ms for hover or press. A slow bounce can be used for a nonessential desktop decoration. Honor `prefers-reduced-motion`, and avoid motion that obscures content or blocks interaction.

### Layout and responsive behavior

- Start with a mobile layout, then expand grids to two or three columns as space allows. A roughly `max-w-5xl` content area, generous gaps, and ample vertical spacing create a sketchbook feel; adapt to dense ticket views, which may need more width and tighter spacing.
- Keep key content and actions available on mobile. Hide or simplify decorative arrows, circles, and connecting lines there. Use appropriate horizontal padding and avoid fixed sizes that cause overflow.
- Vary card angles, organic stat shapes, and occasional overlap to add personality. Preserve clear reading order, keyboard order, and enough space around interactive elements.
- Use the product's real screens and data. Do not add pricing, blog, testimonials, or marketing sections simply because they appeared as visual examples in the source prompt.

## Completion checks

Before finishing frontend work, check the relevant screens at narrow and wide widths, keyboard focus and form behavior, color contrast, reduced-motion behavior, and role-dependent controls. Run the available build or lint checks when the project provides them. Report what changed, how it was checked, and any concrete remaining limitation.
