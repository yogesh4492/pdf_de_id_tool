import express from "express";
import path from "path";
import fs from "fs";
import { execFile } from "child_process";
import multer from "multer";
import { createServer as createViteServer } from "vite";

const app = express();
const PORT = 3000;

// Setup temp and jobs directories
const TEMP_DIR = path.join(process.cwd(), "temp_jobs");
if (!fs.existsSync(TEMP_DIR)) {
  fs.mkdirSync(TEMP_DIR, { recursive: true });
}

// Setup multer for uploading PDFs
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    cb(null, TEMP_DIR);
  },
  filename: (req, file, cb) => {
    const uniqueSuffix = Date.now() + "-" + Math.round(Math.random() * 1e9);
    cb(null, file.fieldname + "-" + uniqueSuffix + ".pdf");
  },
});

const upload = multer({
  storage,
  limits: { fileSize: 25 * 1024 * 1024 }, // 25MB limit
  fileFilter: (req, file, cb) => {
    if (file.mimetype === "application/pdf") {
      cb(null, true);
    } else {
      cb(new Error("Only PDF files are supported!"));
    }
  },
});

// Parse json payloads
app.use(express.json());

// ─────────────────────────────────────────────────────────────
//  API ENDPOINTS
// ─────────────────────────────────────────────────────────────

// Health Check
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", service: "ShieldPDF Engine" });
});

// PDF De-identification API
app.post("/api/deidentify", upload.single("file"), (req, res) => {
  if (!req.file) {
    res.status(400).json({ status: "error", message: "No PDF file uploaded." });
    return;
  }

  const file = req.file;
  const configStr = req.body.config || "{}";
  const jobId = Math.random().toString(36).substring(2, 10);
  const jobDir = path.join(TEMP_DIR, `job_${jobId}`);

  try {
    fs.mkdirSync(jobDir, { recursive: true });

    const inputPath = file.path;
    const outputPath = path.join(jobDir, "redacted.pdf");
    const configPath = path.join(jobDir, "config.json");

    // Write config file
    fs.writeFileSync(configPath, configStr, "utf-8");

    // Execute Python redaction script
    execFile(
      "python3",
      ["redact.py", inputPath, "-o", outputPath, "-c", configPath],
      (error, stdout, stderr) => {
        // Always clean up the uploaded input file to save disk space
        try {
          if (fs.existsSync(inputPath)) {
            fs.unlinkSync(inputPath);
          }
        } catch (cleanupErr) {
          console.error("Failed to clean up uploaded input PDF:", cleanupErr);
        }

        if (error) {
          console.error("Python Execution Error:", stderr || error.message);
          let errMsg = "Failed to run PDF redaction.";
          try {
            // Try parsing python error output if it's JSON
            const errJson = JSON.parse(stdout.trim());
            if (errJson && errJson.status === "error") {
              errMsg = errJson.message;
            }
          } catch (e) {
            errMsg = `Execution failed: ${stderr || error.message}`;
          }

          res.status(500).json({
            status: "error",
            message: errMsg,
          });
          return;
        }

        try {
          const result = JSON.parse(stdout.trim());
          if (result.status === "error") {
            res.status(500).json({
              status: "error",
              message: result.message,
            });
            return;
          }

          // Return successful redaction payload with a dynamic download handle
          res.json({
            ...result,
            job_id: jobId,
          });
        } catch (parseErr) {
          console.error("Failed to parse Python stdout as JSON:", stdout, parseErr);
          res.status(500).json({
            status: "error",
            message: "Internal parser mismatch reading de-identified data.",
          });
        }
      }
    );
  } catch (err: any) {
    console.error("Processing Setup Error:", err);
    res.status(500).json({
      status: "error",
      message: err.message || "Failed to set up de-identification workspace.",
    });
  }
});

// Download Redacted File API
app.get("/api/download/:jobId", (req, res) => {
  const { jobId } = req.params;
  const targetPath = path.join(TEMP_DIR, `job_${jobId}`, "redacted.pdf");

  if (!fs.existsSync(targetPath)) {
    res.status(404).json({ status: "error", message: "File not found or expired." });
    return;
  }

  res.download(targetPath, "de-identified_document.pdf");
});

// ─────────────────────────────────────────────────────────────
//  VITE DEVELOPMENT MIDDLEWARE & STATIC SERVING
// ─────────────────────────────────────────────────────────────

async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Express server running on http://localhost:${PORT}`);
  });
}

startServer().catch((err) => {
  console.error("Failed to boot Express server:", err);
});
