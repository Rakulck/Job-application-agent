import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import path from "path";

const execAsync = promisify(exec);

export async function POST(request: NextRequest) {
  try {
    const { job_id } = await request.json();

    if (!job_id) {
      return NextResponse.json({ error: "job_id is required" }, { status: 400 });
    }

    // Call Python retry script in the background
    const projectRoot = path.resolve(process.cwd(), "..");
    const command = `cd "${projectRoot}" && python -m agent.retry_application --job-id "${job_id}"`;

    // Run in background (non-blocking)
    execAsync(command)
      .then(({ stdout, stderr }) => {
        console.log(`[retry] stdout: ${stdout}`);
        if (stderr) console.error(`[retry] stderr: ${stderr}`);
      })
      .catch((error) => {
        console.error(`[retry] error running script: ${error}`);
      });

    return NextResponse.json({
      success: true,
      message: "Retry queued - check dashboard for updates",
      job_id,
    });
  } catch (error) {
    console.error("Retry endpoint error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "Internal server error" },
      { status: 500 }
    );
  }
}
