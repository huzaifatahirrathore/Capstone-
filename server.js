const express = require("express");
const multer = require("multer");
const axios = require("axios");
const FormData = require("form-data");
const fs = require("fs");
const cors = require("cors");
const pool = require("./db");

const app = express();
app.use(cors());

// store uploaded files temporarily
const upload = multer({ dest: "uploads/" });

/* =========================
   HEALTH ROUTE
========================= */
app.get("/health", (req, res) => {
  res.json({ status: "Node backend running" });
});

/* =========================
   DETECT ROUTE (JSON)
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

    // cleanup uploaded file
    fs.unlink(req.file.path, () => {});

    res.json(response.data);

  } catch (err) {
    console.error("Detect Error:", err.message);
    res.status(500).json({ error: "Detect failed" });
  }
});

/* =========================
   COMPARE ROUTE (IMAGE)
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
      {
        headers: form.getHeaders(),
        responseType: "stream"
      }
    );

    res.setHeader("Content-Type", "image/jpeg");

    response.data.pipe(res);

    // cleanup files after response
    response.data.on("end", () => {
      fs.unlink(req.files["before"][0].path, () => {});
      fs.unlink(req.files["after"][0].path, () => {});
    });

    response.data.on("error", (err) => {
      console.error("Stream error:", err);
      res.status(500).json({ error: "Stream failed" });
    });

  } catch (err) {
    console.error("Compare Error:", err.message);
    res.status(500).json({ error: "Compare failed" });
  }
});

/* =========================
   START SERVER
========================= */
const PORT = 3000;

// ────────────────
// USER CRUD ROUTES
// ────────────────
app.use(express.json());

// Create user
app.post("/users", async (req, res) => {
  const { username, email, password } = req.body;
  if (!username || !email || !password) {
    return res.status(400).json({ error: "Missing fields" });
  }
  try {
    const result = await pool.query(
      `INSERT INTO users (username, email, password)
       VALUES ($1, $2, $3)
       RETURNING id, username, email`,
      [username, email, password]
    );
    res.status(201).json({ user: result.rows[0] });
  } catch (err) {
    console.error("Create User Error:", err.message);
    res.status(500).json({ error: "Create user failed" });
  }
});

// Get all users
app.get("/users", async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT id, username, email FROM users`
    );
    res.json({ users: result.rows });
  } catch (err) {
    console.error("Get Users Error:", err.message);
    res.status(500).json({ error: "Get users failed" });
  }
});

// Get user by ID
app.get("/users/:id", async (req, res) => {
  try {
    const result = await pool.query(
      `SELECT id, username, email FROM users WHERE id = $1`,
      [req.params.id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "User not found" });
    }
    res.json({ user: result.rows[0] });
  } catch (err) {
    console.error("Get User Error:", err.message);
    res.status(500).json({ error: "Get user failed" });
  }
});

// Update user
app.put("/users/:id", async (req, res) => {
  const { username, email } = req.body;
  if (!username || !email) {
    return res.status(400).json({ error: "Missing fields" });
  }
  try {
    const result = await pool.query(
      `UPDATE users SET username = $1, email = $2 WHERE id = $3
       RETURNING id, username, email`,
      [username, email, req.params.id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "User not found" });
    }
    res.json({ user: result.rows[0] });
  } catch (err) {
    console.error("Update User Error:", err.message);
    res.status(500).json({ error: "Update user failed" });
  }
});

// Delete user
app.delete("/users/:id", async (req, res) => {
  try {
    const result = await pool.query(
      `DELETE FROM users WHERE id = $1 RETURNING id`,
      [req.params.id]
    );
    if (result.rows.length === 0) {
      return res.status(404).json({ error: "User not found" });
    }
    res.json({ deleted: result.rows[0].id });
  } catch (err) {
    console.error("Delete User Error:", err.message);
    res.status(500).json({ error: "Delete user failed" });
  }
});

app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});