require("dotenv").config();

const express = require("express");
const multer = require("multer");
const axios = require("axios");
const FormData = require("form-data");
const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const cors = require("cors");
const pool = require("./db");
const jwt = require("jsonwebtoken");
const bcrypt = require("bcryptjs");

const app = express();
app.use(cors());
app.use(express.json());

const upload = multer({ dest: "uploads/" });

const PORT = 3000;
const JWT_SECRET = process.env.JWT_SECRET || "secret_key";
const TRAIN_ROOT = path.resolve(__dirname, "../ML/train");
const TRAIN_PYTHON = path.join(TRAIN_ROOT, ".venv", "bin", "python");
const TRAIN_COMPARE_SCRIPT = path.join(TRAIN_ROOT, "compare.py");
const TRAIN_RESULTS_DIR = path.join(TRAIN_ROOT, "results");

/* =========================
   AUTH MIDDLEWARE
========================= */
function authenticateToken(req, res, next) {
  const authHeader = req.headers["authorization"];

  if (!authHeader) {
    return res.status(401).json({ error: "No token provided" });
  }

  const token = authHeader.split(" ")[1];

  if (!token) {
    return res.status(401).json({ error: "Invalid token format" });
  }

  jwt.verify(token, JWT_SECRET, (err, user) => {
    if (err) {
      return res.status(403).json({ error: "Invalid or expired token" });
    }
    req.user = user;
    next();
  });
}

/* =========================
   HEALTH
========================= */
app.get("/health", (req, res) => {
  res.json({ status: "Node backend running" });
});

/* =========================
   DETECT (Python)
========================= */
app.post("/detect", upload.single("image"), async (req, res) => {
  try {
    const form = new FormData();
    form.append("image", fs.createReadStream(req.file.path));

    const response = await axios.post(
      "http://localhost:5000/detect",
      form,
      { headers: form.getHeaders() }
    );

    fs.unlink(req.file.path, () => {});
    res.json(response.data);

  } catch (err) {
    res.status(500).json({ error: "Detect failed" });
  }
});

/* =========================
   COMPARE (ML/train)
========================= */
function runTrainCompare(beforePath, afterPath) {
  return new Promise((resolve, reject) => {
    const child = spawn(
      TRAIN_PYTHON,
      [TRAIN_COMPARE_SCRIPT, beforePath, afterPath, "--json-output"],
      { cwd: TRAIN_ROOT }
    );

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.on("error", reject);

    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr || `compare.py exited with code ${code}`));
        return;
      }

      // Extract the structured JSON metrics line emitted by --json-output
      let metrics = null;
      for (const line of stdout.split("\n")) {
        if (line.startsWith("JSON_OUTPUT:")) {
          try { metrics = JSON.parse(line.slice("JSON_OUTPUT:".length)); } catch (_) {}
          break;
        }
      }

      resolve({ stdout, metrics });
    });
  });
}

async function getCompareOutputPath(beforePath, afterPath) {
  const beforeStem = path.parse(beforePath).name;
  const afterStem  = path.parse(afterPath).name;
  const prefix     = `compare_${beforeStem}_vs_${afterStem}_`;

  // compare.py appends the vegetation method tag (e.g. ExG+Otsu, ExG, HSV)
  // so we scan the results dir for any .jpg matching our prefix instead of
  // hardcoding the tag.
  await fs.promises.mkdir(TRAIN_RESULTS_DIR, { recursive: true });
  const files = await fs.promises.readdir(TRAIN_RESULTS_DIR);
  const match = files.find(f => f.startsWith(prefix) && f.endsWith(".jpg"));

  if (!match) {
    throw new Error(`Compare output not found for stems: ${beforeStem} vs ${afterStem}`);
  }
  return path.join(TRAIN_RESULTS_DIR, match);
}

app.post("/compare", upload.fields([
  { name: "before" },
  { name: "after" }
]), async (req, res) => {
  try {
    const beforeFile = req.files["before"]?.[0];
    const afterFile = req.files["after"]?.[0];

    if (!beforeFile || !afterFile) {
      return res.status(400).json({ error: "Both before and after images are required" });
    }

    const beforePath = path.resolve(beforeFile.path);
    const afterPath = path.resolve(afterFile.path);

    const { metrics } = await runTrainCompare(beforePath, afterPath);
    const outputPath = await getCompareOutputPath(beforePath, afterPath);

    const imageBuffer = await fs.promises.readFile(outputPath);
    const imageBase64 = imageBuffer.toString("base64");

    res.json({
      imageDataUrl: `data:image/jpeg;base64,${imageBase64}`,
      metrics: metrics || null,
    });
  } catch (err) {
    res.status(500).json({ error: err.message || "Compare failed" });
  }
});

/* =========================
   USER CRUD
========================= */

// Create user (hashed password)
app.post("/users", async (req, res) => {
  try {
    const { username, email, password } = req.body;

    const hashedPassword = await bcrypt.hash(password, 10);

    const result = await pool.query(
      `INSERT INTO users (username, email, password)
       VALUES ($1, $2, $3)
       RETURNING id, username, email`,
      [username, email, hashedPassword]
    );

    res.status(201).json(result.rows[0]);

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get all users (PROTECTED)
app.get("/users", authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT id, username, email FROM users`
    );
    res.json(result.rows);

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Get user by ID
app.get("/users/:id", async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT id, username, email FROM users WHERE id=$1`,
      [req.params.id]
    );

    if (result.rows.length === 0) {
      return res.status(404).json({ error: "User not found" });
    }

    res.json(result.rows[0]);

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Update user
app.put("/users/:id", async (req, res) => {
  try {
    const { username, email } = req.body;

    const result = await pool.query(
      `UPDATE users SET username=$1, email=$2
       WHERE id=$3
       RETURNING id, username, email`,
      [username, email, req.params.id]
    );

    res.json(result.rows[0]);

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Delete user
app.delete("/users/:id", async (req, res) => {
  try {
    const result = await pool.query(
      `DELETE FROM users WHERE id=$1 RETURNING id`,
      [req.params.id]
    );

    res.json({ deleted: result.rows[0] });

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/* =========================
   SIGNUP
========================= */
app.post("/signup", async (req, res) => {
  try {
    const { username, email, password } = req.body;

    const exists = await pool.query(
      `SELECT id FROM users WHERE email=$1`,
      [email]
    );

    if (exists.rows.length > 0) {
      return res.status(409).json({ error: "Email already exists" });
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    const result = await pool.query(
      `INSERT INTO users (username, email, password)
       VALUES ($1,$2,$3)
       RETURNING id, username, email`,
      [username, email, hashedPassword]
    );

    const token = jwt.sign(
      { id: result.rows[0].id, email },
      JWT_SECRET,
      { expiresIn: "1h" }
    );

    res.status(201).json({ user: result.rows[0], token });

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/* =========================
   LOGIN
========================= */
app.post("/login", async (req, res) => {
  try {
    const { email, password } = req.body;

    const result = await pool.query(
      `SELECT * FROM users WHERE email=$1`,
      [email]
    );

    if (result.rows.length === 0) {
      return res.status(401).json({ error: "Invalid credentials" });
    }

    const user = result.rows[0];

    const valid = await bcrypt.compare(password, user.password);

    if (!valid) {
      return res.status(401).json({ error: "Invalid credentials" });
    }

    const token = jwt.sign(
      { id: user.id, email: user.email },
      JWT_SECRET,
      { expiresIn: "1h" }
    );

    delete user.password;

    res.json({ user, token });

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

/* =========================
   PLANTATION PROJECT CRUD
========================= */
// Create plantation project
app.post("/projects", authenticateToken, async (req, res) => {
  const { name, description, location, start_date, end_date } = req.body;
  if (!name) {
    return res.status(400).json({ error: "Project name is required" });
  }
  try {
    const result = await pool.query(
      `INSERT INTO plantation_projects (name, description, location, start_date, end_date, created_by)
       VALUES ($1, $2, $3, $4, $5, $6)
       RETURNING *`,
      [name, description, location, start_date, end_date, req.user.id]
    );
    res.status(201).json({ project: result.rows[0] });
  } catch (err) {
    res.status(500).json({ error: "Create project failed" });
  }
});

// Get all plantation projects
app.get("/projects", authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT * FROM plantation_projects`
    );
    res.json({ projects: result.rows });
  } catch (err) {
    res.status(500).json({ error: "Get projects failed" });
  }
});

// Get plantation project by ID
app.get("/projects/:id", authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT * FROM plantation_projects WHERE id = $1`,
      [req.params.id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "Project not found" });
    }
    res.json({ project: result.rows[0] });
  } catch (err) {
    res.status(500).json({ error: "Get project failed" });
  }
});

// Update plantation project
app.put("/projects/:id", authenticateToken, async (req, res) => {
  const { name, description, location, start_date, end_date } = req.body;
  try {
    const result = await pool.query(
      `UPDATE plantation_projects SET name = $1, description = $2, location = $3, start_date = $4, end_date = $5
       WHERE id = $6 RETURNING *`,
      [name, description, location, start_date, end_date, req.params.id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "Project not found" });
    }
    res.json({ project: result.rows[0] });
  } catch (err) {
    res.status(500).json({ error: "Update project failed" });
  }
});

// Delete plantation project
app.delete("/projects/:id", authenticateToken, async (req, res) => {
  try {
    const result = await pool.query(
      `DELETE FROM plantation_projects WHERE id = $1 RETURNING id`,
      [req.params.id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "Project not found" });
    }
    res.json({ deleted: result.rows[0].id });
  } catch (err) {
    res.status(500).json({ error: "Delete project failed" });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});