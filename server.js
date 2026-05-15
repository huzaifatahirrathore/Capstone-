require("dotenv").config();

const express = require("express");
const multer = require("multer");
const axios = require("axios");
const FormData = require("form-data");
const fs = require("fs");
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
   COMPARE (Python)
========================= */
app.post("/compare", upload.fields([
  { name: "before" },
  { name: "after" }
]), async (req, res) => {
  try {
    const form = new FormData();

    form.append("before", fs.createReadStream(req.files["before"][0].path));
    form.append("after", fs.createReadStream(req.files["after"][0].path));

    const response = await axios.post(
      "http://localhost:5000/compare",
      form,
      { headers: form.getHeaders(), responseType: "stream" }
    );

    res.setHeader("Content-Type", "image/jpeg");
    response.data.pipe(res);

  } catch (err) {
    res.status(500).json({ error: "Compare failed" });
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

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});