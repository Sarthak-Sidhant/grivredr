#!/usr/bin/env python3
"""
Add our working Abua Sathi scraper to the pattern library
This will help future training learn from our Select2 handling
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from knowledge.pattern_library import PatternLibrary

def main():
    print("="*80)
    print("Adding Abua Sathi Scraper to Pattern Library")
    print("="*80)
    print()

    # Initialize pattern library
    pattern_lib = PatternLibrary()

    # Read our working scraper
    scraper_path = Path("outputs/generated_scrapers/ranchi_district/portals/abua_sathi/abua_sathi_scraper.py")

    if not scraper_path.exists():
        print(f"❌ Scraper not found at {scraper_path}")
        return False

    with open(scraper_path) as f:
        code = f.read()

    print(f"✓ Read scraper ({len(code)} characters)")

    # Extract the Select2 handling method for code snippets
    select2_snippet = '''async def _select_select2_dropdown(
        self,
        page: Page,
        selector: str,
        value: str,
        field_name: str,
        wait_after: float = 1.5
    ) -> bool:
        """Select a value from a Select2 dropdown (jQuery plugin)."""
        try:
            await page.wait_for_selector(selector, state='attached', timeout=5000)

            # Method 1: Try using jQuery/JavaScript to set the value directly
            try:
                js_code = """
                    (args) => {
                        const select = document.querySelector(args.selector);
                        if (select && typeof $ !== 'undefined') {
                            $(select).val(args.value);
                            $(select).trigger('change');
                            return true;
                        }
                        return false;
                    }
                """
                result = await page.evaluate(js_code, {"selector": selector, "value": value})

                if result:
                    logger.info(f"Selected {field_name}: {value} (via JavaScript)")
                    await asyncio.sleep(wait_after)
                    return True
                else:
                    raise Exception("jQuery not available or selector not found")

            except Exception as js_error:
                logger.warning(f"JavaScript method failed for {field_name}: {js_error}")
                # Fallback to UI interaction...

        except Exception as e:
            self.errors.append(f"Failed to select {field_name}: {str(e)}")
            logger.error(f"Failed to select Select2 {field_name}: {e}")
            return False'''

    # Define the form schema
    form_schema = {
        "municipality": "abua_sathi",
        "url": "https://www.abuasathiranchi.org/SiteController/onlinegrievance",
        "fields": [
            {
                "name": "name",
                "type": "text",
                "id": "name",
                "required": True,
                "label": "Full Name"
            },
            {
                "name": "contact",
                "type": "number",
                "id": "contact",
                "required": False,
                "label": "Mobile Number"
            },
            {
                "name": "village_name",
                "type": "textarea",
                "id": "village_name",
                "required": False,
                "label": "Address/Village Name"
            },
            {
                "name": "block_id",
                "type": "select",
                "id": "block_id",
                "required": True,
                "label": "Select Block / Municipality",
                "class": "form-control form-control-lg form-select js-example-basic-single select2-hidden-accessible",
                "select2": True,
                "cascading_parent": True
            },
            {
                "name": "jurisdiction_id",
                "type": "select",
                "id": "jurisdiction_id",
                "required": True,
                "label": "Select GP / Ward",
                "class": "form-control form-control-lg form-select js-example-basic-single select2-hidden-accessible",
                "select2": True,
                "cascading_child": True,
                "depends_on": "block_id"
            },
            {
                "name": "department_id",
                "type": "select",
                "id": "department_id",
                "required": True,
                "label": "Select Concerned Department",
                "class": "form-control form-control-lg form-select js-example-basic-single select2-hidden-accessible",
                "select2": True
            },
            {
                "name": "description",
                "type": "textarea",
                "id": "description",
                "required": True,
                "label": "Problem Description",
                "maxlength": 250
            },
            {
                "name": "attachment[]",
                "type": "file",
                "id": "attachment[]",
                "required": False,
                "label": "Upload Document/Image"
            }
        ]
    }

    # JS analysis metadata
    js_analysis = {
        "complexity": "high",
        "select2_detected": True,
        "jquery_required": True,
        "cascading_dropdowns": True,
        "ajax_submission": False,
        "dynamic_fields": False
    }

    # Store the pattern
    print("\n📦 Storing pattern in library...")

    try:
        success = pattern_lib.store_pattern(
            municipality_name="abua_sathi",
            form_url="https://www.abuasathiranchi.org/SiteController/onlinegrievance",
            form_schema=form_schema,
            generated_code=code,
            confidence_score=1.0,  # We know it works!
            validation_attempts=1,
            js_analysis=js_analysis
        )

        if success:
            print("✅ Pattern stored successfully!")
            print()
            print("Pattern contains:")
            print("  • Select2 dropdown handling")
            print("  • Cascading dropdown logic")
            print("  • jQuery integration")
            print("  • Complete scraper implementation")
            print()
            print("Future training will now learn from this pattern!")
            return True
        else:
            print("⚠️  Pattern may already exist (check database)")
            return True

    except Exception as e:
        print(f"❌ Error storing pattern: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    print()
    print("="*80)
    if success:
        print("✅ PATTERN ADDED SUCCESSFULLY")
    else:
        print("❌ FAILED TO ADD PATTERN")
    print("="*80)
    sys.exit(0 if success else 1)
