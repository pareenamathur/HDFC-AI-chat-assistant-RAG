---
name: Groww RAG Chatbot System
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#3a3939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#bacac1'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#85948c'
  outline-variant: '#3c4a43'
  surface-tint: '#2fe0aa'
  primary: '#44edb7'
  on-primary: '#003828'
  primary-container: '#00d09c'
  on-primary-container: '#00533c'
  inverse-primary: '#006c4f'
  secondary: '#ffb955'
  on-secondary: '#452b00'
  secondary-container: '#dc9100'
  on-secondary-container: '#4f3100'
  tertiary: '#ffc8a3'
  on-tertiary: '#502500'
  tertiary-container: '#ffa15b'
  on-tertiary-container: '#733800'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#59fdc5'
  primary-fixed-dim: '#2fe0aa'
  on-primary-fixed: '#002116'
  on-primary-fixed-variant: '#00513b'
  secondary-fixed: '#ffddb4'
  secondary-fixed-dim: '#ffb955'
  on-secondary-fixed: '#291800'
  on-secondary-fixed-variant: '#633f00'
  tertiary-fixed: '#ffdcc6'
  tertiary-fixed-dim: '#ffb785'
  on-tertiary-fixed: '#301400'
  on-tertiary-fixed-variant: '#713700'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
typography:
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Inter
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.01em
  label-sm:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 4px
  xs: 8px
  sm: 12px
  md: 16px
  lg: 24px
  xl: 32px
  container-max: 800px
  gutter: 16px
---

## Brand & Style

This design system is engineered to evoke a sense of **precision, financial authority, and modern technical sophistication**. It leverages the core Groww brand identity—characterized by its signature green and deep charcoal tones—to create a high-trust environment for RAG-driven financial interactions.

The aesthetic follows a **Modern-Corporate** philosophy with a focus on flat, high-contrast surfaces. The interface prioritizes legibility and rapid information scanning, using "Groww Green" sparingly but purposefully to guide user actions and highlight key insights. The design remains grounded and utilitarian, avoiding unnecessary ornamentation to ensure the focus remains on data accuracy and financial clarity.

## Colors

The palette is rooted in a true-dark ecosystem, utilizing specific hex values to create a structured hierarchy of information:

- **Core Canvas**: The primary background uses `#0D0D0D` to ensure absolute contrast with text and UI elements.
- **Layering**: Surfaces use `#1C1C1E` for cards and `#151515` for subtle structural separation.
- **Precision Accents**: `#00D09C` (Groww Green) is reserved for primary actions, success states, and key data points. 
- **Attention & Caution**: `#F5A623` (Disclaimer Amber) is strictly used for financial disclaimers and regulatory warnings to ensure they are visually distinct from the standard chat flow.
- **Typography**: Text follows a strict hierarchy where `#F5F5F5` provides high-legibility for content, while `#A0A0A0` is used for metadata and secondary labels.

## Typography

This design system utilizes **Inter** exclusively to maintain a systematic, utilitarian aesthetic. 

- **Headings**: Use Bold (700) weight with tighter letter spacing for a punchy, professional look. Large headlines scale down for mobile to a maximum of 20px to prevent overflow.
- **UI & Interaction**: Regular (400) weight is used for long-form AI responses to maximize readability. Medium (500) weight is applied to buttons, labels, and UI controls for better definition against dark surfaces.
- **Financial Data**: Small labels and mono-style numerical data should use the Label-SM style to maintain a precise, technical feel.

## Layout & Spacing

The system employs a **centered fluid layout** optimized for reading comfort. 

- **Chat Container**: The main chat thread is constrained to an 800px max-width to maintain optimal line lengths for RAG-generated content.
- **Rhythm**: A 4px base unit ensures mathematical precision across all padding and margins. 
- **Mobile**: On smaller viewports, the layout shifts to a 16px side margin with fluid components. 
- **Spacing Logic**: Larger gaps (24px-32px) are used to separate distinct AI responses, while tighter spacing (8px-12px) is used for elements within a single message card (e.g., text vs. source citations).

## Elevation & Depth

Depth in this design system is achieved through **tonal layering and crisp outlines** rather than traditional shadows. 

- **Surface Tiers**: The lowest layer is the page background (#0D0D0D). Interactive or content-heavy elements sit on the Surface (#1C1C1E). 
- **Outlines**: Every card and input field must feature a 1px solid border (#2A2A2A). This creates a "blueprint" aesthetic that communicates precision.
- **No Shadows**: To maintain the flat, modern look, drop shadows are entirely omitted. Elevation is communicated solely through color contrast and border definition.
- **Active States**: When an element is focused or active (like an input field), the border transitions from the neutral border color to the primary Groww Green (#00D09C).

## Shapes

The shape language is a hybrid of **friendly organic curves and functional geometric containers**:

- **Chat Bubbles**: Utilize an 18px radius on all corners to provide a soft, approachable feel for dialogue.
- **Pills/Buttons**: Primary action buttons and category filters use a 100px "pill" radius, signifying a clear, tappable area in line with the main Groww mobile app.
- **Structural Cards**: Layout containers and surfaces use a more restrained 12px radius to maintain a professional, structured appearance.

## Components

- **Buttons**: Primary buttons are solid Groww Green (#00D09C) with black text. Secondary buttons are outlined (#2A2A2A) with primary text (#F5F5F5). All use the 100px pill shape.
- **Chat Input**: A fixed bottom bar using the Surface color (#1C1C1E) and a continuous 1px border (#2A2A2A). It should feel integrated into the shell rather than floating.
- **RAG Source Chips**: Small, pill-shaped indicators with #1C1C1E backgrounds and #A0A0A0 text, allowing users to trace the AI's logic without distracting from the main answer.
- **Disclaimers**: Financial disclaimers are housed in a container with a subtle #F5A623 (Amber) left-border accent, using secondary text sizing.
- **Cards**: Surface-colored (#1C1C1E) with no shadow. Used for complex data displays like stock charts or fund comparisons generated by the RAG engine.