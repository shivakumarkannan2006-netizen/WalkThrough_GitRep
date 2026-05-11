# Tech Stack Setup - UI/UX Specification

## Overview

Complete visual and interaction specification for the new 3-step tech stack setup flow.

---

## Step 1: Technology Selection

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ← Back to Dashboard                                        │
│                                                             │
│  New Site Evaluation                                        │
│  Select your AI site builder and hosting platform, choose  │
│  your analysis approach, then enter your URL to begin...   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 1. Select your tech stack          [3 selected]     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  AI Site Builders   ⚡                                       │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                      │
│  │      │ │      │ │  ✓   │ │      │                      │
│  │Love- │ │Base44│ │Replit│ │Bolt. │                      │
│  │able  │ │      │ │      │ │new   │                      │
│  └──────┘ └──────┘ └──────┘ └──────┘                      │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                      │
│  │      │ │      │ │      │ │      │                      │
│  │ v0   │ │Cursor│ │Wind- │ │Copilot                     │
│  │      │ │      │ │surf  │ │      │                      │
│  └──────┘ └──────┘ └──────┘ └──────┘                      │
│                                                             │
│  Hosting & Deployment   ☁️                                  │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐                      │
│  │      │ │  ✓   │ │      │ │      │                      │
│  │Rail- │ │Render│ │Vercel│ │ AWS  │                      │
│  │way   │ │      │ │      │ │      │                      │
│  └──────┘ └──────┘ └──────┘ └──────┘                      │
│                                                             │
│                                                             │
│  [====== Continue to Analysis Mode ======]                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Card Styling

**Unselected Card (AI Builder)**
```
┌─────────────────┐
│                 │  border: 2px solid #e5e7eb (gray-200)
│    Lovable      │  background: white
│                 │  hover: border-teal-300, bg-teal-50
└─────────────────┘
```

**Selected Card (AI Builder)**
```
┌═════════════════┐
│      ✓          │  border: 2px solid #14b8a6 (teal-500)
│    Lovable      │  background: #f0fdfa (teal-50)
│                 │  checkmark: top-right, teal-600
└═════════════════┘
```

**Unselected Card (Hosting)**
```
┌─────────────────┐
│                 │  border: 2px solid #e5e7eb (gray-200)
│    Railway      │  background: white
│                 │  hover: border-blue-300, bg-blue-50
└─────────────────┘
```

**Selected Card (Hosting)**
```
┌═════════════════┐
│      ✓          │  border: 2px solid #3b82f6 (blue-500)
│    Railway      │  background: #eff6ff (blue-50)
│                 │  checkmark: top-right, blue-600
└═════════════════┘
```

### Responsiveness
- Desktop (≥1024px): 4 columns
- Tablet (768px-1023px): 4 columns
- Mobile (<768px): 2 columns
- Gap between cards: 12px (Tailwind: `gap-3`)
- Padding per card: 16px (`p-4`)

### Typography
- Section header: font-medium, text-gray-900, 14px
- Card text: font-medium, text-gray-900, 14px
- Icon: 16px (Tailwind: `w-4 h-4`)

---

## Step 2: Analysis Mode Selection

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard                                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 2. Choose your analysis approach                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌───────────────────────────────────────────────────┐     │
│  │ ✓ Finding Errors                                  │     │
│  │   Identify issues in your codebase                │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
│  ┌───────────────────────────────────────────────────┐     │
│  │ ☐ Finding Errors & Fixes                          │     │
│  │   Identify issues and provide solutions           │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
│  ┌───────────────────────────────────────────────────┐     │
│  │ ☐ Finding, Fixing & Pushing to GitHub             │     │
│  │   Complete workflow with GitHub integration       │     │
│  │   MCP Integration Ready                           │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
│  ┌───────────────────────────────────────────────────┐     │
│  │ ☐ Finding, Fixing & Fixing in Builder             │     │
│  │   Direct AI builder integration                   │     │
│  │   MCP Integration Ready                           │     │
│  │   Direct AI builder integration available         │     │
│  └───────────────────────────────────────────────────┘     │
│                                                             │
│  [Back] ......................... [Continue]              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Mode Card Styling

**Unselected**
```
┌────────────────────────────────┐
│ ☐ Mode Label                   │  border: 2px solid #e5e7eb
│   Description text             │  background: white
│   Optional: MCP note           │  hover: border-teal-300
└────────────────────────────────┘  padding: 20px (p-5)
```

**Selected**
```
┌════════════════════════════════┐
│ ✓ Mode Label                   │  border: 2px solid #14b8a6
│   Description text             │  background: #f0fdfa
│   Optional: MCP note           │  checkmark: teal-600
└════════════════════════════════┘
```

### MCP Indicator Badge
```
Location: Below description (mt-2)
Style: text-xs, text-teal-600, font-normal
Text: "MCP Integration Ready"
Conditional: Show only if requiresMCP === true
```

### Platform-Specific Badge
```
Location: Below MCP badge (mt-1)
Style: text-xs, text-amber-600, font-normal
Text: "Direct AI builder integration available"
Conditional: Show only if Lovable/Base44/Replit selected
```

### Responsiveness
- Max-width: 600px
- Full width on mobile
- Stack vertically
- Space between: 12px (`space-y-3`)

---

## Step 3: Website Details

### Layout
```
┌─────────────────────────────────────────────────────────────┐
│  ← Back to Dashboard                                        │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 3. Enter your website details                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────┐      │
│  │                                                  │      │
│  │ Site Name (optional)                             │      │
│  │ ┌──────────────────────────────────────────────┐ │      │
│  │ │ My Awesome Project                         │ │      │
│  │ └──────────────────────────────────────────────┘ │      │
│  │                                                  │      │
│  │ Website URL (required)                           │      │
│  │ ┌──────────────────────────────────────────────┐ │      │
│  │ │ https://your-site.com                      │ │      │
│  │ └──────────────────────────────────────────────┘ │      │
│  │ The crew will crawl this URL and all reachable   │      │
│  │ sub-pages.                                       │      │
│  │                                                  │      │
│  └──────────────────────────────────────────────────┘      │
│                                                             │
│  [Back] .............................. [Start Audit]       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Input Styling

**Site Name Input**
```
Background: #f9fafb (gray-50)
Border: 1px solid #e5e7eb (gray-200)
Focus border: #14b8a6 (teal-500)
Padding: 10px 16px (py-2.5 px-4)
Border radius: 8px
Font: 14px
```

**URL Input (Valid)**
```
Background: #f9fafb (gray-50)
Border: 1px solid #e5e7eb (gray-200)
Focus border: #14b8a6 (teal-500)
Padding: 10px 16px (py-2.5 px-4)
Border radius: 8px
Font: 14px
```

**URL Input (Invalid)**
```
Background: #f9fafb (gray-50)
Border: 1px solid #f87171 (red-400)
Focus border: #ef4444 (red-500)
```

### Helper Text
```
Color: #9ca3af (gray-400)
Size: 12px (text-xs)
Margin: 6px above (mt-1.5)
```

### Error Messages
```
Display: If validation fails
Color: #dc2626 (red-500)
Size: 12px (text-xs)
Margin: 8px above (mt-2)
Role: alert
```

---

## Buttons & Controls

### Back Button
```
Style: Secondary (outlined)
Color: border-gray-200, text-gray-700
Hover: border-gray-400, text-gray-900
Width: 50% on desktop, full-width below
```

### Continue Button
```
Style: Primary (solid)
Color: bg-teal-600, text-white
Hover: bg-teal-700
Disabled: opacity-50, cursor-not-allowed
Width: 50% on desktop, full-width below
```

### Start Audit Button
```
Style: Primary (solid)
Icon: Play icon
Color: bg-teal-600, text-white
Hover: bg-teal-500
Disabled: opacity-40
Loading: "Saving…" text
```

---

## Color Palette

### Primary
- Teal 500: `#14b8a6` - Selection, Focus
- Teal 600: `#0d9488` - Primary action, Selected state
- Teal 700: `#0f766e` - Hover state
- Teal 50: `#f0fdfa` - Background for selected

### Secondary
- Blue 500: `#3b82f6` - Hosting selection
- Blue 600: `#2563eb` - Hosting selected
- Blue 50: `#eff6ff` - Hosting background

### Tertiary (MCP/Platform)
- Amber 600: `#d97706` - Platform-specific badge
- Teal 600: `#0d9488` - MCP badge

### Neutral
- Gray 50: `#f9fafb` - Input background
- Gray 200: `#e5e7eb` - Border
- Gray 400: `#9ca3af` - Helper text
- Gray 500: `#6b7280` - Icons
- Gray 600: `#4b5563` - Labels
- Gray 900: `#111827` - Headings, main text

### States
- Success: `#10b981` (not used in this step)
- Warning: `#f59e0b` (not used in this step)
- Error: `#dc2626` - Validation errors
- Red 50: `#fef2f2` - Error background
- Red 400: `#f87171` - Error border

---

## Animations & Transitions

### Card Selection
```
Type: border-color, background-color
Duration: 150ms
Easing: ease-in-out (Tailwind: transition)
```

### Button Hover
```
Type: background-color, border-color
Duration: 150ms
Easing: ease-in-out
```

### Input Focus
```
Type: border-color
Duration: 100ms
Easing: ease-in-out
```

---

## Accessibility

### Keyboard Navigation
- Tab: Move between focusable elements
- Shift+Tab: Move backwards
- Enter/Space: Select card/button
- Escape: None (no modal dismiss)

### ARIA Attributes
- `role="alert"` - Error messages
- `aria-busy="true"` - Loading state on button
- `aria-label` - For icon-only buttons (if any)
- `aria-describedby` - For input helper text (future)

### Screen Reader
- Card labels announced on focus
- Error messages announced automatically
- Button disabled state announced
- Mode descriptions fully readable

### Color Contrast
- Text on white: ≥4.5:1
- Border on white: ≥3:1
- Text on colored bg: ≥4.5:1
All WCAG AA compliant

---

## Breakpoints

### Desktop (≥1024px)
- Max-width container: 896px (`max-w-4xl`)
- Grid columns: 4
- Button width: auto
- Side-by-side layout

### Tablet (768px - 1023px)
- Max-width container: 100%
- Grid columns: 4
- Button width: auto
- Single column forms

### Mobile (<768px)
- Max-width container: 100%
- Padding: 16px (`px-4`)
- Grid columns: 2
- Full-width buttons
- Stack buttons vertically

---

## Icons Used

- Back: `ArrowLeft` (4x4)
- Selection indicator: `CheckCircle` (20x20)
- AI Builder section: `Zap` (amber)
- Hosting section: `Cloud` (blue)
- Play button: `Play` (4x4)
- Error icon: AlertTriangle (implied context)

---

## Spacing System

All spacing uses 4px base unit:
- p-4: 16px
- p-5: 20px
- p-6: 24px
- gap-2: 8px
- gap-3: 12px
- mb-4: 16px
- mb-5: 20px
- mb-6: 24px
- mt-1: 4px
- mt-1.5: 6px
- mt-2: 8px

---

## Future Enhancements

- [ ] Add company logos/icons to tech cards
- [ ] Show "recommended combinations"
- [ ] Add platform-specific documentation links
- [ ] Implement smooth scroll to errors
- [ ] Add success animation on submission

---

## Notes

- All transitions use `transition` class from Tailwind
- Card interaction uses pointer cursor
- Disabled buttons use `not-allowed` cursor
- Loading state shows spinner (implement as needed)
- Error states validated before submission
