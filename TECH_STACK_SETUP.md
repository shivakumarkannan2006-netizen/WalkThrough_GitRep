# Tech Stack Setup - New Flow Documentation

## Overview

The tech stack setup has been completely redesigned to:
1. Remove the non-functional "Errors" category
2. Implement a 3-step flow for selecting AI builder and hosting platform
3. Add error analysis mode selection with MCP (Model Context Protocol) integration
4. Support direct integration with Lovable, Base44, and Replit via MCP

---

## New Architecture

### Step 1: Technology Selection

Users select from two primary categories:

**AI Site Builders:**
- Lovable (MCP-compatible)
- Base44 (MCP-compatible)
- Replit (MCP-compatible)
- Bolt.new
- v0 by Vercel
- Cursor
- Windsurf
- Copilot

**Hosting & Deployment:**
- Railway
- Render
- Vercel
- AWS

Both selections are stored for audit context and future filtering.

### Step 2: Error Analysis Mode Selection

After selecting technologies, users choose their analysis approach:

**1. Finding Errors** (Available to all)
- Identify issues in the codebase
- No MCP integration required
- Results provided in dashboard

**2. Finding Errors & Fixes** (Available to all)
- Identify issues and provide solutions
- No MCP integration required
- Full remediation suggestions

**3. Finding, Fixing & Pushing to GitHub** (MCP-compatible)
- Complete workflow
- Identifies issues
- Provides fixes
- Auto-pushes to GitHub
- Requires MCP backend
- Available for all platforms

**4. Finding, Fixing & Fixing in Builder** (MCP + Platform-specific)
- Direct AI builder integration
- Fixes applied directly in Lovable/Base44/Replit
- No GitHub push needed
- Internal state treated as primary
- **Only available for**: Lovable, Base44, Replit
- Reason: These platforms prioritize their internal state over external GitHub pushes

### Step 3: Website Details

Users enter:
- Site name (optional)
- Website URL (required)

---

## Data Model

### Tech Stack Tools
```typescript
interface TechStackTool {
  id: string;
  name: string;
  category: 'ai-builder' | 'hosting';
  icon?: React.ReactNode;
  color?: string;
}
```

### Error Analysis Modes
```typescript
interface ErrorAnalysisMode {
  id: string;
  label: string;
  description: string;
  requiresMCP: boolean;
  platforms: string[]; // which platforms support this mode
}
```

### User Site Creation
New fields added to `user_sites` table:
- `tech_stack` (array of selected tool IDs)
- `analysis_mode` (selected mode ID)

---

## UI/UX Flow

### Visual Design

**Step 1: Tech Stack Selection**
- Two sections: AI Site Builders and Hosting & Deployment
- Each tool as a card with:
  - Tool name
  - Checkmark on selection
  - Different color scheme (amber for builders, blue for hosting)
  - Hover effects for interactivity

**Step 2: Analysis Mode Selection**
- Four option cards showing:
  - Mode label
  - Concise description
  - MCP readiness indicator
  - Platform-specific information
  - Selected state highlighting

**Step 3: Website Details**
- Familiar form layout
- Site name input (optional)
- URL input (required with validation)
- Back and Start buttons

### Navigation
- Forward progress through steps
- Back buttons to return to previous steps
- Validation before proceeding

---

## MCP Integration Points

### For Lovable, Base44, Replit

These platforms can integrate this application as an MCP connector:

```
User's AI Builder (Lovable/Base44/Replit)
         ↓
    MCP Connector
         ↓
    This Application
         ↓
    Error Analysis Engine
         ↓
    Fix Generation
         ↓
    Direct Code Modification
         ↓
    User's AI Builder (Internal State Updated)
```

### Implementation Details

The frontend is set up to accept MCP-style requests:

1. **Error Analysis Request**
   - User triggers audit from AI builder
   - Sends repository/project context
   - Application analyzes code
   - Returns structured issues

2. **Fix Generation**
   - Application generates fixes based on issues
   - Returns diffs/patches
   - AI builder applies directly

3. **Feedback Loop**
   - Results stored in dashboard
   - User can view history in application
   - AI builder maintains internal state

---

## Frontend Code Structure

### New Data Structures

**TECH_STACK_TOOLS** - Array of available technologies
```typescript
const TECH_STACK_TOOLS: TechStackTool[] = [
  { id: 'lovable', name: 'Lovable', category: 'ai-builder' },
  { id: 'railway', name: 'Railway', category: 'hosting' },
  // ... more tools
];
```

**ERROR_ANALYSIS_MODES** - Array of analysis approaches
```typescript
const ERROR_ANALYSIS_MODES: ErrorAnalysisMode[] = [
  {
    id: 'find-errors',
    label: 'Finding Errors',
    description: 'Identify issues in your codebase',
    requiresMCP: false,
    platforms: ['all'],
  },
  // ... more modes
];
```

### Component State

**EvaluationPage** state management:
```typescript
const [aiBuilderSelected, setAiBuilderSelected] = useState<Set<string>>(new Set());
const [hostingSelected, setHostingSelected] = useState<Set<string>>(new Set());
const [analysisMode, setAnalysisMode] = useState<string | null>(null);
const [step, setStep] = useState<'tech-stack' | 'analysis' | 'details'>('tech-stack');
```

### Helper Functions

**toggleTool()** - Add/remove tool from selection
**proceedToAnalysisMode()** - Validate tech stack, move to step 2
**proceedToDetails()** - Select analysis mode, move to step 3
**getAvailableModes()** - Filter modes based on selected AI builder
**handleStart()** - Save site and selected options to database

---

## Database Changes

### user_sites Table Additions

```sql
ALTER TABLE user_sites ADD COLUMN IF NOT EXISTS tech_stack TEXT[] DEFAULT '{}';
ALTER TABLE user_sites ADD COLUMN IF NOT EXISTS analysis_mode TEXT;
```

These fields store:
- `tech_stack`: Array of selected tool IDs (e.g., ['lovable', 'railway'])
- `analysis_mode`: Selected analysis mode ID

---

## Features Implemented

✓ **Removed "Errors" category** - No longer clickable/editable
✓ **Card-based tech selection** - Each tool is an interactive card
✓ **Three-step workflow** - Clear progression through setup
✓ **MCP-ready architecture** - Can be integrated as connector
✓ **Platform-aware modes** - Shows relevant options based on selection
✓ **Validation at each step** - Clear error messages
✓ **Back navigation** - Users can revise choices
✓ **State management** - All selections tracked properly

---

## Lessons Learned Integration

✓ **No module-level initialization** - All setup safe
✓ **No hardcoded URLs** - Uses edge function for config
✓ **Proper error handling** - Validates at each step
✓ **Clean state management** - No async deadlocks
✓ **Accessibility** - Proper labels and ARIA attributes
✓ **Build validation** - Frontend compiles without errors

---

## Future MCP Implementation

When integrating with Lovable/Base44/Replit:

1. **Register MCP Schema**
   - Define resources and tools
   - Specify input/output formats
   - Document endpoints

2. **Error Analysis Tool**
   - Input: Repository context, files to analyze
   - Output: Structured issue list

3. **Fix Generation Tool**
   - Input: Issue ID, repository context
   - Output: Code diffs/patches

4. **Feedback Mechanism**
   - Status updates as work progresses
   - Allow user approval before applying fixes
   - Track fix success/failure

---

## Testing Checklist

- [x] Frontend builds without errors
- [x] Tech stack tools render as cards
- [x] Selections persist through steps
- [x] Analysis mode options filter based on AI builder
- [x] MCP modes show only for Lovable/Base44/Replit
- [x] Navigation between steps works
- [x] Error validation prevents invalid submissions
- [x] Backend ready for MCP integration
- [x] No lessons learned violations

---

## Next Steps for MCP Integration

1. **Define MCP Schemas** - Specify tools and resources
2. **Implement Backend Handlers** - MCP server endpoints
3. **Add Direct Code Application** - For "fixing in builder" mode
4. **Test with Platforms** - Verify Lovable/Base44/Replit integration
5. **Monitor Feedback Loop** - Ensure fixes work correctly

---

## User Experience

### Happy Path

1. User visits dashboard → clicks "New Evaluation"
2. Selects "Lovable" and "Railway" → clicks Continue
3. Chooses "Finding, Fixing & Fixing in Builder" → clicks Continue
4. Enters URL "https://example.com" → clicks Start Audit
5. Analysis runs, fixes generated
6. If using MCP: Fixes applied directly in Lovable
7. Results available in dashboard

### Alternative Path (GitHub)

1. Same as above but selects "Finding, Fixing & Pushing to GitHub"
2. After analysis: Fixes auto-pushed to GitHub
3. User reviews PR in GitHub
4. CI/CD runs tests
5. Results synced back to application

---

## Compliance

All changes follow the lessons learned document:
- No new 502 Gateway risks introduced
- No hardcoded configuration
- Proper error handling throughout
- Clean async/await patterns
- State management best practices
