"""Export the FastAPI OpenAPI schema to a JSON file."""

import json
import sys
from pathlib import Path

from app.main import app


def main():
    if len(sys.argv) > 1:
        output_path = Path(sys.argv[1])
    else:
        output_path = Path(__file__).parent.parent.parent / "docs" / "openapi.json"
        
    schema = app.openapi()
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, sort_keys=True)
        f.write("\n")
        
    print(f"OpenAPI schema exported to {output_path.resolve()}")

if __name__ == "__main__":
    main()
