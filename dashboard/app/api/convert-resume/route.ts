import { NextRequest, NextResponse } from "next/server";
import { execSync } from "child_process";
import fs from "fs";
import path from "path";
import os from "os";

export async function POST(req: NextRequest) {
  let tempFilePath = "";

  try {
    const formData = await req.formData();
    const file = formData.get("file") as File;

    if (!file) {
      return NextResponse.json(
        { error: "No file provided" },
        { status: 400 }
      );
    }

    if (!file.name.endsWith(".docx")) {
      return NextResponse.json(
        { error: "Only .docx files are supported" },
        { status: 400 }
      );
    }

    // Write file to temp directory
    const tempDir = os.tmpdir();
    tempFilePath = path.join(tempDir, `resume_${Date.now()}.docx`);
    const buffer = await file.arrayBuffer();
    fs.writeFileSync(tempFilePath, Buffer.from(buffer));

    // Create a converter wrapper script
    const converterScript = path.join(
      process.cwd(),
      "..",
      "agent",
      "convert_wrapper.py"
    );

    // Create wrapper script if it doesn't exist
    const wrapperCode = `import sys
import json
from docx_converter import docx_to_json

docx_path = sys.argv[1]
try:
    result = docx_to_json(docx_path)
    print(json.dumps(result))
except Exception as e:
    print(json.dumps({"error": str(e)}), file=sys.stderr)
    sys.exit(1)
`;

    if (!fs.existsSync(converterScript)) {
      fs.writeFileSync(converterScript, wrapperCode);
    }

    let output = "";
    try {
      output = execSync(`python "${converterScript}" "${tempFilePath}"`, {
        encoding: "utf-8",
        maxBuffer: 10 * 1024 * 1024, // 10MB buffer
        cwd: path.join(process.cwd(), "..", "agent"),
      });
    } catch (error: any) {
      const stderr = error.stderr?.toString() || error.message;
      console.error("[convert-resume] Python error:", stderr);
      throw new Error(`Conversion failed: ${stderr}`);
    }

    // Parse result
    const resumeJson = JSON.parse(output.trim());

    // Clean up temp file
    if (fs.existsSync(tempFilePath)) {
      fs.unlinkSync(tempFilePath);
    }

    return NextResponse.json({
      success: true,
      resume: resumeJson,
    });
  } catch (error) {
    // Clean up temp file on error
    if (tempFilePath && fs.existsSync(tempFilePath)) {
      try {
        fs.unlinkSync(tempFilePath);
      } catch (e) {
        // Ignore cleanup errors
      }
    }

    console.error("[convert-resume] error:", error);
    const errorMsg = error instanceof Error ? error.message : "Unknown error";
    return NextResponse.json(
      {
        error: `Failed to convert resume: ${errorMsg}. Ensure file is a valid DOCX.`,
      },
      { status: 500 }
    );
  }
}
