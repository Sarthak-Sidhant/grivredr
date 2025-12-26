# Training System Improvements

## Issues Identified from Abua Sathi Training Test

### 1. **CRITICAL: Token Limit Too Low (Line 680 Cutoff)**

**Problem**: Code generation cuts off at ~680 lines because `max_tokens=6000`

**Files to Fix**:
- `agents/code_generator_agent.py` line 329
- `agents/code_generator_agent.py` line 418
- `agents/code_generator_agent.py` line 534

**Solution**:
```python
# Change from:
max_tokens=6000

# To:
max_tokens=16000  # Claude can handle up to 200k context, 16k output is safe
```

**Why 16000?**:
- Our manual scraper is ~800 lines
- With docstrings and methods: ~12-14k tokens
- 16k gives headroom for complete generation

---

### 2. **CRITICAL: Markdown Code Fence Issue**

**Problem**: Generated code starts with ```python and ends with ```, causing syntax errors

**Root Cause**: The prompt says "Generate ONLY the Python code" but Claude still wraps it

**Files to Fix**:
- `agents/code_generator_agent.py` lines 321-322

**Solution**:
```python
# Change prompt ending from:
"""
Generate ONLY the Python code. No explanations, just the complete class.
"""

# To:
"""
CRITICAL: Return ONLY raw Python code with NO markdown formatting.
- Do NOT wrap in ```python or ``` code fences
- Do NOT include any explanations before or after the code
- Start directly with the imports and class definition
- End with the last closing brace of the class

The code will be saved directly to a .py file, so it must be pure Python.
"""
```

**Additional Fix**: The regex extraction (lines 352-360) works BUT the header is added BEFORE checking if extraction worked. Fix:

```python
# After line 360, before adding header:
if not code.strip().startswith('import') and not code.strip().startswith('"""'):
    logger.warning("Generated code doesn't start with imports, might have markdown")
```

---

### 3. **MAJOR: Pattern Library Not Learning Select2**

**Problem**: Pattern library exists but doesn't store/retrieve Select2 patterns

**Files to Fix**:
- `knowledge/pattern_library.py` - needs to extract and store code snippets
- `agents/code_generator_agent.py` - needs to actually USE retrieved patterns

**Current Flow**:
```
1. Code generator asks pattern library for similar patterns
2. Pattern library says "No similar patterns found"
3. Code generator generates from scratch (misses Select2 handling)
```

**Solution A - Store Our Working Scraper as Pattern**:

Create script to manually add our working scraper:

```python
# scripts/add_pattern_to_library.py
from knowledge.pattern_library import PatternLibrary
from pathlib import Path

pattern_lib = PatternLibrary()

# Read our working scraper
with open('generated_scrapers/ranchi_district/portals/abua_sathi/abua_sathi_scraper.py') as f:
    code = f.read()

# Extract the Select2 handling method
select2_snippet = """
async def _select_select2_dropdown(self, page, selector, value, field_name, wait_after=1.5):
    # jQuery/JavaScript method
    js_code = '''
        (args) => {
            const select = document.querySelector(args.selector);
            if (select && typeof $ !== 'undefined') {
                $(select).val(args.value);
                $(select).trigger('change');
                return true;
            }
            return false;
        }
    '''
    result = await page.evaluate(js_code, {"selector": selector, "value": value})
    await asyncio.sleep(wait_after)
    return result
"""

# Store pattern
pattern_lib.store_pattern(
    municipality_name="abua_sathi",
    form_url="https://www.abuasathiranchi.org/SiteController/onlinegrievance",
    form_schema={
        "fields": [
            {"name": "block_id", "type": "select", "class": "select2-hidden-accessible"},
            {"name": "jurisdiction_id", "type": "select", "class": "select2-hidden-accessible"},
            {"name": "department_id", "type": "select", "class": "select2-hidden-accessible"}
        ]
    },
    generated_code=code,
    confidence_score=1.0,
    validation_attempts=1,
    js_analysis={"complexity": "high", "select2_detected": True}
)
```

**Solution B - Improve Pattern Retrieval**:

In `agents/code_generator_agent.py`, the retrieved pattern needs to be INJECTED into the prompt:

```python
# Around line 250, after pattern_library.find_similar_patterns():

if similar_patterns:
    pattern_context = "\\n\\nIMPORTANT - Learn from these similar scrapers:\\n"
    for pattern in similar_patterns[:2]:  # Top 2 patterns
        if 'select2' in str(pattern.get('code_snippets', {})):
            pattern_context += f"""
This scraper handles Select2 dropdowns using jQuery:
{pattern['code_snippets'].get('select2_handler', '')}

Use this same approach for Select2 dropdowns (class contains 'select2-hidden-accessible').
"""

    # ADD pattern_context to the prompt before sending to Claude
    prompt = prompt + pattern_context
```

---

### 4. **MEDIUM: Pattern Detection Logic**

**Problem**: Form signature matching isn't catching similar forms

**Files to Fix**:
- `knowledge/pattern_library.py` lines 150-200 (find_similar_patterns method)

**Current Logic**:
- Creates hash of field names/types
- Only matches EXACT same forms

**Better Logic**:
```python
def find_similar_patterns(self, form_schema, js_complexity=None, limit=3):
    # 1. Check for Select2 indicators
    has_select2 = any(
        'select2' in field.get('class', '').lower()
        for field in form_schema.get('fields', [])
    )

    # 2. If has Select2, prioritize patterns that also have Select2
    if has_select2:
        query = '''
            SELECT * FROM patterns
            WHERE metadata LIKE '%select2%'
            ORDER BY success_rate DESC, confidence_score DESC
            LIMIT ?
        '''

    # 3. Also match by JS complexity
    # ... existing logic
```

---

### 5. **MINOR: System Prompt for Code Generation**

**Problem**: Prompt doesn't explicitly mention Select2

**Files to Fix**:
- `agents/code_generator_agent.py` line 270-320

**Add to Prompt**:
```python
**Handling Select2 Dropdowns:**
If any select element has class 'select2-hidden-accessible', use jQuery to interact:

```python
await page.evaluate('''
    (args) => {
        const select = document.querySelector(args.selector);
        $(select).val(args.value).trigger('change');
    }
''', {"selector": "#field_id", "value": "field_value"})
await asyncio.sleep(1.5)  # Wait for cascading
```

DO NOT use page.select_option() for Select2 dropdowns - it will timeout!
```

---

## Implementation Priority

### Phase 1 - Critical Fixes (30 minutes)
1. ✅ Increase max_tokens to 16000
2. ✅ Fix markdown code fence prompt
3. ✅ Add pattern for our working Abua Sathi scraper

### Phase 2 - Pattern Learning (1 hour)
4. ✅ Improve pattern retrieval to inject Select2 snippets
5. ✅ Update find_similar_patterns to detect Select2
6. ✅ Add Select2 handling to generation prompt

### Phase 3 - Testing (30 minutes)
7. ✅ Re-run training on Abua Sathi
8. ✅ Verify complete generation (>680 lines)
9. ✅ Verify Select2 handling present
10. ✅ Test generated scraper works

---

## Expected Improvements

After fixes:
- ✅ Complete scraper generation (no cutoff)
- ✅ No markdown syntax errors
- ✅ Select2 dropdowns handled correctly
- ✅ Pattern library actually used
- ✅ Cascading dropdowns working
- ✅ Generated scraper passes tests

**Estimated Success Rate**: 90%+ (up from current 60%)

---

## How to Apply Fixes

Run this script to apply all fixes:
```bash
# 1. Create improvement script
python scripts/improve_trainer.py

# 2. Add our working scraper as pattern
python scripts/add_abua_sathi_pattern.py

# 3. Re-train and test
python train_cli.py abua_sathi_v2 https://www.abuasathiranchi.org/SiteController/onlinegrievance
```
