# Agentic Training Example: Smart Ranchi Form

## 🎬 Live Training Session Walkthrough

### Initial State
```
URL: https://smartranchi.in/Portal/View/ComplaintRegistration.aspx?m=Online
Municipality: Ranchi
Training Status: Not Started
Human: Sidhant (supervising)
```

---

## 🤖 Agent Training Log

### Attempt #1: Initial Exploration

**[FormDiscoveryAgent]** Starting exploration...

```
Action: Navigate to URL
Status: ✅ Page loaded

Action: Take screenshot for Claude Vision
Status: ✅ Screenshot captured

Action: Analyzing with Claude Vision...
```

**[Claude Vision Response]**
```json
{
  "form_title": "Register Your Complaint",
  "sections": [
    {
      "section": "Complainant Details",
      "fields": [
        {"label": "Problem", "type": "text", "selector": "#problem", "required": true},
        {"label": "Select Type", "type": "dropdown", "selector": "#type", "required": false},
        {"label": "Mobile No", "type": "text", "selector": "#mobile", "required": true},
        {"label": "Email ID", "type": "text", "selector": "#email", "required": false},
        {"label": "Residential Address", "type": "textarea", "selector": "#address", "required": false},
        {"label": "Remarks", "type": "textarea", "selector": "#remarks", "required": false}
      ]
    },
    {
      "section": "Upload Document / Image",
      "fields": [
        {"label": "Select File Type", "type": "dropdown", "selector": "#filetype", "required": false},
        {"label": "File Upload", "type": "file", "selector": "#fileupload", "required": false}
      ]
    }
  ],
  "submit_button": {"text": "Register Complaint", "selector": "button[type='submit']"}
}
```

**[FormDiscoveryAgent]** Vision analysis complete. Found 8 fields.

**[FormDiscoveryAgent]** 🤔 Reflection: I should verify this by actually interacting...

---

### Attempt #2: Interactive Discovery

**[FormDiscoveryAgent]** Testing dropdown interactions...

```
Action: Click "Select Type" dropdown
Result: ❌ Dropdown appears empty in HTML but...

Action: Trigger 'click' event
Result: ✅ Options appeared dynamically!

Discovered Options:
  - Electrical
  - Water Supply
  - Roads
  - Sanitation
  - Street Lights
  - Others

Analysis: This dropdown is populated by JavaScript on click.
```

**[FormDiscoveryAgent]** 🤔 There's a "Problem" field but it looks like a dropdown, not text input. Let me recheck...

```
Action: Inspect "Problem" field more carefully
Result: ✅ It's actually a dropdown that depends on "Select Type"!

Discovery: "Problem" dropdown is populated based on "Select Type" selection
- This is a cascading dropdown pattern
- "Problem" won't populate until "Select Type" is chosen
```

**[FormDiscoveryAgent]** Updating schema with cascading dependency...

---

### Attempt #3: Validation Discovery

**[TestAgent]** Now let me test what's actually required...

```
Test: Submit form with all fields empty
Action: Click "Register Complaint"

Result: ❌ Validation errors appeared

Captured Errors:
  - "Please enter Mobile No."
  - "Please Select Type"
  - "Please select Problem"

Analysis:
  ✅ Mobile is required (confirmed)
  ✅ Select Type is required (Vision missed this!)
  ✅ Problem is required (Vision thought it was optional)
```

**[TestAgent]** Updating required field flags...

**[FormDiscoveryAgent]** 🤔 I noticed "Contact Person No" and "Contact Person Name" fields. Let me check if they're required...

```
Test: Submit with main fields filled but Contact Person empty
Result: ✅ Form accepted

Conclusion: Contact Person fields are optional
```

---

### Attempt #4: Field Discovery Missed Fields

**[FormDiscoveryAgent]** Wait, I see more fields in the screenshot that I didn't capture...

```
Action: Re-scan DOM for input fields
Discovered:
  - "Contact Person No" (text input)
  - "Contact Person Name" (text input)
  - "Tenament No" (text input)

Analysis: These fields were below the fold or loaded dynamically
```

**[FormDiscoveryAgent]** 📝 Note to self: Always scroll and check for lazy-loaded fields

---

### Attempt #5: JavaScript Analysis

**[JSAnalyzer]** Analyzing form submission logic...

```
Injected monitor code:
  - Tracking XHR requests
  - Monitoring form events
  - Capturing validation functions

Action: Fill form and submit

Captured:
  1. Form onsubmit() validates fields client-side
  2. If validation passes, makes POST request to:
     /Portal/Ajax/RegisterComplaint
  3. Response contains: {"success": true, "complaintId": "RMC123456"}
  4. Page shows tracking ID on success

JavaScript Patterns Detected:
  - Client-side validation before submit
  - AJAX submission (not standard form POST)
  - Dynamic tracking ID display
```

**[JSAnalyzer]** ⚠️  Important: This is an AJAX form, not standard POST!

---

### Attempt #6: Human Review

**[TrainingUI]** 🙋 Showing discovered schema to human...

**Flask Dashboard Display:**
```
┌──────────────────────────────────────────────────────────┐
│ Training Session: Smart Ranchi Complaint Form            │
├──────────────────────────────────────────────────────────┤
│                                                           │
│ Agent's Understanding:                                    │
│                                                           │
│ Required Fields:                                          │
│   ✓ Select Type (dropdown)                              │
│   ✓ Problem (dropdown, depends on Type)                 │
│   ✓ Mobile No (text, validation: 10 digits)             │
│                                                           │
│ Optional Fields:                                          │
│   ○ Email ID                                             │
│   ○ Residential Address                                  │
│   ○ Remarks                                              │
│   ○ Contact Person No                                    │
│   ○ Contact Person Name                                  │
│   ○ Tenament No                                          │
│   ○ File Upload (with Select File Type dropdown)        │
│                                                           │
│ Submission Method: AJAX POST to /Portal/Ajax/...        │
│                                                           │
│ [Human Review]                                            │
│ Does this look correct? [Yes] [No, I'll fix it]         │
│                                                           │
│ Any fields missing? [Add Field]                          │
│ Any fields wrong? [Edit Field]                           │
│                                                           │
│ Special instructions:                                     │
│ [ Optional text box for human hints ]                    │
│                                                           │
│ [Looks Good - Generate Scraper] [Agent Retry]           │
└──────────────────────────────────────────────────────────┘
```

**[Human: Sidhant]** Reviewing...

```
Human Feedback:
  ✅ Fields look correct
  ✅ Required/optional detection is accurate
  ✅ Cascading dropdown logic understood
  📝 Note: "Please always fill Contact Person fields for faster resolution"