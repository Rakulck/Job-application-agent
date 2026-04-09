import sys
import json
from docx_converter import docx_to_json

docx_path = sys.argv[1]
try:
    result = docx_to_json(docx_path)
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({"error": str(e)}), file=sys.stderr)
    sys.exit(1)
